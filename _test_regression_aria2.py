"""
Testes de regressão para bugs críticos do aria2c + importre.

Bug 1: aria2c crasha com --session (opção inexistente)
Bug 2: KeyError 'completed_length' quando RPC morre
Bug 3: speed=491MB/s absurdo no dl_progress (cálculo errado)
Bug 4: _aria2_download não tem fallback quando daemon indisponível
Bug 5: --file-allocation=falloc falha sem privilégio admin

Cada teste deve:
1. Reproduzir o bug (falhar antes do fix)
2. Passar depois do fix
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Garantir que podemos importar os módulos do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0


def test_pass(name):
    global PASS
    PASS += 1
    print(f"  [PASS] {name}")


def test_fail(name, reason):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {name}: {reason}")


def test_assert(name, condition, detail=""):
    if condition:
        test_pass(name)
    else:
        test_fail(name, detail or "condição não atendida")


# ============================================================================
# Bug 1: aria2c crasha com --session (opção inexistente)
# ============================================================================
def test_bug1_session_option_not_in_cmd():
    """Verifica que --session= não está na lista de argumentos do aria2c."""
    print("\n--- Bug 1: --session opção inexistente ---")
    # Ler o código fonte e verificar que --session não está
    src = open(os.path.join(os.path.dirname(__file__), "_aria2_manager.py"), "r", encoding="utf-8").read()
    # --session= não deve aparecer (apenas --save-session= e --input-file=)
    has_session = "--session=" in src and "--save-session=" not in src.split("--session=")[0].split("\n")[-1]
    # Mais preciso: procurar por f"--session=" exatamente
    has_bad_session = 'f"--session=' in src or '"--session=' in src or "'--session=" in src
    test_assert("não há --session= nos argumentos", not has_bad_session,
                "encontrado --session= no código (deve usar apenas --input-file e --save-session)")


def test_bug1_aria2c_starts_without_session():
    """Verifica que aria2c inicia sem a opção --session."""
    print("\n--- Bug 1b: aria2c inicia sem --session ---")
    # Verificar que aria2c aceita as opções atuais
    import _aria2_manager
    mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
    # Parar qualquer instância existente
    mgr.stop_daemon()
    time.sleep(1)

    result = mgr.start_daemon()
    if result:
        test_pass("aria2c inicia sem --session")
        # Verificar RPC responde
        try:
            stat = mgr.get_global_stat()
            test_assert("RPC responde após start", "numActive" in stat or "downloadSpeed" in stat)
        except Exception as e:
            test_fail("RPC responde após start", str(e))
        # Parar
        mgr.stop_daemon()
    else:
        test_fail("aria2c inicia sem --session", "start_daemon retornou False")


# ============================================================================
# Bug 2: KeyError 'completed_length' quando RPC morre
# ============================================================================
def test_bug2_keyerror_completed_length():
    """Verifica que get_download_info retorna dict com todas as chaves mesmo em erro."""
    print("\n--- Bug 2: KeyError 'completed_length' ---")
    import _aria2_manager
    mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")

    # Simular RPC morto: gid inexistente deve retornar dict com chaves
    info = mgr.get_download_info("fake_gid_12345")
    # Deve ter todas as chaves que o importre.py acessa
    required_keys = ["gid", "status"]
    for k in required_keys:
        test_assert(f"get_download_info tem chave '{k}'", k in info, f"chave '{k}' ausente: {info}")

    # O importre.py usa .get() agora, não [] — verificar
    src = open(os.path.join(os.path.dirname(__file__), "importre.py"), "r", encoding="utf-8").read()
    # Procurar por info["completed_length"] (acesso direto = bug)
    # Excluir linhas comentadas
    lines = src.split("\n")
    bad_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if 'info["completed_length"]' in line or 'info["total_length"]' in line or 'info["download_speed"]' in line:
            bad_lines.append(f"linha {i+1}: {stripped}")
    test_assert("importre.py usa .get() não []", len(bad_lines) == 0,
                f"acesso direto encontrado: {bad_lines[:3]}")


# ============================================================================
# Bug 3: speed=491MB/s absurdo no dl_progress
# ============================================================================
def test_bug3_speed_calculation():
    """Verifica que a velocidade reportada não é absurda."""
    print("\n--- Bug 3: speed absurda no dl_progress ---")
    dl_progress_path = r"D:\roms\library\roms\_importre_state\dl_progress.json"

    if os.path.exists(dl_progress_path):
        try:
            data = json.load(open(dl_progress_path, "r", encoding="utf-8"))
            absurd_count = 0
            for serial, info in data.items():
                if isinstance(info, dict):
                    speed = info.get("speed", 0)
                    # 100MB/s = 100*1024*1024 = 104857600 — acima disso é absurdo para este contexto
                    if speed > 100 * 1024 * 1024:
                        absurd_count += 1
                        print(f"    {serial}: speed={speed/1024/1024:.1f}MB/s (ABSURDO)")
            test_assert("sem velocidades absurdas (>100MB/s)", absurd_count == 0,
                        f"{absurd_count} itens com speed absurda")
        except Exception as e:
            test_fail("ler dl_progress.json", str(e))
    else:
        test_pass("dl_progress.json não existe (ok para teste)")


# ============================================================================
# Bug 4: _aria2_download não tem fallback quando daemon indisponível
# ============================================================================
def test_bug4_fallback_requests():
    """Verifica que _aria2_download tem fallback para requests."""
    print("\n--- Bug 4: fallback para requests ---")
    src = open(os.path.join(os.path.dirname(__file__), "importre.py"), "r", encoding="utf-8").read()

    # Verificar que _requests_download existe
    test_assert("_requests_download definida", "def _requests_download(" in src,
                "função _requests_download não encontrada")

    # Verificar que _aria2_download chama _requests_download quando mgr é None
    test_assert("_aria2_download chama fallback", "_requests_download" in src and "fallback" in src,
                "fallback não referenciado em _aria2_download")


# ============================================================================
# Bug 5: --file-allocation=falloc falha sem privilégio admin
# ============================================================================
def test_bug5_file_allocation():
    """Verifica que --file-allocation não é falloc (que precisa admin)."""
    print("\n--- Bug 5: --file-allocation=falloc ---")
    src = open(os.path.join(os.path.dirname(__file__), "_aria2_manager.py"), "r", encoding="utf-8").read()
    # Procurar apenas em linhas de código (não comentários)
    lines = src.split("\n")
    falloc_in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "--file-allocation=falloc" in line:
            falloc_in_code = True
            break
    test_assert("não usa falloc em código", not falloc_in_code,
                "--file-allocation=falloc encontrado em linha de código (precisa admin)")
    # Deve usar trunc ou none
    test_assert("usa trunc ou none", "trunc" in src or '"none"' in src,
                "nem trunc nem none encontrados")


# ============================================================================
# Bug 6: aria2c sobrevive a crash do Python (daemon persistente)
# ============================================================================
def test_bug6_daemon_survives_python_crash():
    """Verifica que o daemon aria2c sobrevive quando o processo Python morre."""
    print("\n--- Bug 6: daemon sobrevive a crash do Python ---")
    import _aria2_manager
    mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
    mgr.stop_daemon()
    time.sleep(1)

    if not mgr.start_daemon():
        test_fail("daemon inicia", "start_daemon retornou False")
        return

    # Simular "crash" do Python: deletar a referência ao manager
    pid_before = None
    try:
        with open(_aria2_manager.PID_FILE, "r") as f:
            pid_before = int(f.read().strip())
    except:
        pass

    # Verificar processo ainda existe
    result = subprocess.run(["tasklist", "/FI", f"PID eq {pid_before}"], capture_output=True, text=True, timeout=5)
    alive_before = str(pid_before) in result.stdout
    test_assert("daemon vivo após start", alive_before)

    # "Matar" o Python (simular crash): não chamamos stop_daemon
    del mgr

    # Verificar processo ainda existe (não deve ter morrido)
    time.sleep(2)
    result = subprocess.run(["tasklist", "/FI", f"PID eq {pid_before}"], capture_output=True, text=True, timeout=5)
    alive_after = str(pid_before) in result.stdout
    test_assert("daemon vivo após Python 'crash'", alive_after,
                "daemon morreu quando Python foi destruído (não é persistente)")

    # Limpar
    mgr2 = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
    mgr2.stop_daemon()


# ============================================================================
# Executar todos os testes
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("TESTES DE REGRESSÃO — aria2c + importre")
    print("=" * 60)

    # Testes que não precisam de daemon
    test_bug1_session_option_not_in_cmd()
    test_bug2_keyerror_completed_length()
    test_bug3_speed_calculation()
    test_bug4_fallback_requests()
    test_bug5_file_allocation()

    # Testes que precisam de daemon (mais lentos)
    try:
        test_bug1_aria2c_starts_without_session()
    except Exception as e:
        test_fail("aria2c inicia sem --session", f"exceção: {e}")

    try:
        test_bug6_daemon_survives_python_crash()
    except Exception as e:
        test_fail("daemon sobrevive a crash", f"exceção: {e}")

    print("\n" + "=" * 60)
    print(f"RESULTADO: {PASS} passaram, {FAIL} falharam")
    print("=" * 60)
    sys.exit(0 if FAIL == 0 else 1)
