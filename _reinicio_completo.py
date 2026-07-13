"""Reinicio completo e seguro do sistema PSX.

Use este script apos reiniciar o Devin/IDE.
Ele faz tudo de forma ordenada:
1. Para processos antigos nas portas 8765/8766
2. Corrige referencias de .cue quebradas
3. Realimenta a fila do importre com downloads pendentes
4. Inicia o importre (downloader + supervisor)
5. Inicia o conversor CHD
6. Verifica se tudo subiu
"""
import json
import subprocess
import sys
import time
from pathlib import Path

PSX_DIR = Path(__file__).parent
STATE_DIR = PSX_DIR.parent / "_importre_state"


def log(msg):
    print(f"[REINICIO] {msg}")


def get_pids_on_port(port):
    try:
        proc = subprocess.run(
            ["powershell", "-Command",
             f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"],
            capture_output=True, text=True, timeout=5
        )
        return [int(x) for x in proc.stdout.strip().splitlines() if x.strip().isdigit()]
    except Exception as e:
        log(f"Erro ao verificar porta {port}: {e}")
        return []


def kill_pid(pid):
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True, timeout=5)
        log(f"Processo PID {pid} encerrado")
        return True
    except Exception as e:
        log(f"Erro ao encerrar PID {pid}: {e}")
        return False


def stop_existing_systems():
    log("Parando sistemas antigos...")
    for port in [8765, 8766]:
        for pid in get_pids_on_port(port):
            kill_pid(pid)
    # Tambem matar processos python relacionados
    try:
        proc = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Select-Object ProcessId, CommandLine | Format-Table -AutoSize"],
            capture_output=True, text=True, timeout=10
        )
        import re
        for line in proc.stdout.splitlines():
            if any(x in line for x in ["importre", "chd_convert", "start_system", "supervisor"]):
                m = re.match(r"\s*(\d+)", line)
                if m:
                    kill_pid(int(m.group(1)))
    except Exception as e:
        log(f"Erro ao buscar processos python: {e}")
    time.sleep(2)


def run_script(name):
    script = PSX_DIR / name
    if not script.exists():
        log(f"Script nao encontrado: {script}")
        return False
    log(f"Executando {name}...")
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=120)
    if proc.stdout:
        log(proc.stdout.strip())
    if proc.stderr:
        log(f"STDERR: {proc.stderr.strip()}")
    return proc.returncode == 0


def get_no_window_kwargs():
    """Retorna kwargs para subprocess.Popen/run sem janela e sem roubar foco no Windows."""
    kwargs = {}
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_BREAKAWAY_FROM_JOB
        )
    return kwargs


def start_background_process(script_name, *args):
    script = PSX_DIR / script_name
    if not script.exists():
        log(f"Script nao encontrado: {script}")
        return None
    log(f"Iniciando {script_name} {' '.join(args)}...")
    kwargs = get_no_window_kwargs()
    kwargs.setdefault("stdout", subprocess.DEVNULL)
    kwargs.setdefault("stderr", subprocess.DEVNULL)
    proc = subprocess.Popen(
        [sys.executable, str(script)] + list(args),
        **kwargs,
    )
    return proc.pid


def verify_ports():
    time.sleep(3)
    log("Verificando portas...")
    ok = True
    for port in [8765, 8766]:
        pids = get_pids_on_port(port)
        if pids:
            log(f"  Porta {port}: OK (PID {pids[0]})")
        else:
            log(f"  Porta {port}: LIVRE (falha!)")
            ok = False
    return ok


def main():
    log("=== REINICIO COMPLETO DO SISTEMA PSX ===")
    stop_existing_systems()
    
    # Corrigir CUEs quebrados
    run_script("_fix_cue_references.py")
    
    # Realimentar fila
    run_script("_prepare_requeue.py")
    
    # Iniciar importre
    start_background_process("start_system.py")
    
    # Iniciar conversor CHD
    start_background_process("_chd_convert_v2.py", "--workers", "4")
    
    # Verificar
    if verify_ports():
        log("=== SISTEMA REINICIADO COM SUCESSO ===")
        log("Dashboards:")
        log("  Importre: http://127.0.0.1:8765")
        log("  Conversor CHD: http://127.0.0.1:8766")
    else:
        log("=== ALGO FALHOU - VERIFICAR MANUALMENTE ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
