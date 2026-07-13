#!/usr/bin/env python3
"""Testa CHDs no DuckStation headless com timeout.
Janela oculta (SW_HIDE + CREATE_NO_WINDOW) — nao rouba foco.

Uso:
  python _duck_test.py                    # testa todos
  python _duck_test.py --limit 100        # testa apenas 100
  python _duck_test.py --timeout 8        # timeout de 8s por CHD
  python _duck_test.py --workers 3        # 3 instancias em paralelo
  python _duck_test.py --resume           # continuar de onde parou
"""
import subprocess
import sys
import time
import os
import re
import json
import argparse
import ctypes
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Constantes Windows ---
SW_HIDE = 0
STARTF_USESHOWWINDOW = 0x00000001
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008

PSX = Path(r"D:\roms\library\roms\psx")
DUP = PSX / "duplicados"
DUCK = r"C:\Users\Usuario\AppData\Local\Programs\DuckStation\duckstation-qt-x64-ReleaseLTCG.exe"
DUCK_SETTINGS = Path(r"C:\Users\Usuario\Documents\DuckStation\settings.ini")
DUCK_LOG_DIR = Path(r"C:\Users\Usuario\Documents\DuckStation")
DUCK_LOG_FILE = DUCK_LOG_DIR / "duckstation.log"
RESULTS_FILE = PSX / "_duck_test_results.json"
LOG_FILE = PSX / "_duck_test.log"
CLEANUP_LOG = PSX / "_duck_cleanup.log"
DELETED_FILE = PSX / "_duck_deleted.json"

# Extensoes de ROMs de origem que podem ser apagadas apos CHD confirmado
ROM_SOURCE_EXTS = {".bin", ".cue", ".img", ".iso", ".mdf", ".sub", ".ccd"}
# Extensoes que NUNCA apagar
KEEP_EXTS = {".chd", ".ecm", ".part", ".tmp", ".crdownload", ".json", ".md", ".txt"}

ERROR_PATTERNS = [
    "E/CDROM",           # Error-level CDROM messages
    "E/System",          # Error-level System messages
    "E/Core",            # Error-level Core messages
    "E/BIOS",            # Error-level BIOS messages
    "E/GPU",             # Error-level GPU messages
    "failed to load cd",
    "failed to open cd",
    "could not open disc",
    "not a valid chd",
    "chd error",
    "corrupt chd",
    "no tracks found",
    "failed to parse cue",
    "invalid disc image",
    "unsupported chd",
]

# Padroes que NAO sao erro (warnings benignos)
IGNORE_PATTERNS = [
    "shader cache index",
    "eacces",
    "are you running two instances",
    "failed to open shader cache",
]

# Lock para garantir que so uma instancia leia/escreva o log do Duck por vez
import threading
_duck_log_lock = threading.Lock()


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def cleanup_log(msg):
    """Log dedicado para limpeza de arquivos."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(CLEANUP_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def extract_serial(filename):
    """Extrai serial de um nome de arquivo. Ex: Metal-Slug-X-SLUS-01212.chd -> SLUS-01212"""
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', filename, re.I)
    if m:
        return m.group(1).upper()
    return None


def normalize_name(filename):
    """Normaliza nome para matching: remove serial, hifens->espacos, lowercase."""
    name = re.sub(r'[A-Z]{2,4}[-]\d{3,5}', '', filename, flags=re.I)
    name = name.replace('-', ' ').replace('_', ' ').replace('.', ' ')
    name = re.sub(r'\s+', ' ', name).strip().lower()
    # Remover disc/volume
    name = re.sub(r'\b(disc|volume|vol)\s*\d+\b', '', name)
    return name.strip()


def load_deleted_registry():
    """Carrega registro de arquivos ja apagados."""
    if DELETED_FILE.exists():
        try:
            return json.loads(DELETED_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_deleted_registry(registry):
    """Salva registro de arquivos apagados."""
    try:
        DELETED_FILE.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    except Exception:
        pass


_deleted_lock = threading.Lock()


def cleanup_source_files(chd_path):
    """Apaga arquivos de origem (BIN/CUE/IMG/ISO) correspondentes a um CHD confirmado.
    Procura na pasta principal e em duplicados por serial ou nome similar.
    Retorna (num_deleted, bytes_freed)."""
    chd_name = Path(chd_path).stem
    chd_serial = extract_serial(chd_name)
    chd_norm = normalize_name(chd_name)
    chd_file = Path(chd_path)

    deleted = []
    bytes_freed = 0

    # Pastas onde procurar arquivos de origem
    search_dirs = [PSX, DUP] if DUP.exists() else [PSX]

    for search_dir in search_dirs:
        for f in search_dir.iterdir():
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in ROM_SOURCE_EXTS:
                continue
            # Nunca apagar se for o proprio CHD
            if f.resolve() == chd_file.resolve():
                continue

            # Match por serial (mais confiavel)
            f_serial = extract_serial(f.name)
            matched = False
            if chd_serial and f_serial and chd_serial == f_serial:
                matched = True
            # Se nao tem serial, tentar match por nome normalizado
            if not matched and chd_norm:
                f_norm = normalize_name(f.stem)
                # Match se nome normalizado e igual ou um contem o outro (>= 10 chars)
                if f_norm and (f_norm == chd_norm or
                              (len(f_norm) >= 10 and len(chd_norm) >= 10 and
                               (f_norm in chd_norm or chd_norm in f_norm))):
                    matched = True

            if matched:
                try:
                    size = f.stat().st_size
                    f.unlink()
                    deleted.append(str(f))
                    bytes_freed += size
                    cleanup_log(f"  DELETED {f.name} ({size/1024/1024:.1f}MB) [{chd_name}]")
                except Exception as e:
                    cleanup_log(f"  ERROR deleting {f.name}: {e}")

    # Atualizar registro
    if deleted:
        with _deleted_lock:
            registry = load_deleted_registry()
            for d in deleted:
                registry[d] = {"chd": chd_name, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
            save_deleted_registry(registry)

    return (len(deleted), bytes_freed)


def get_chd_list():
    """Retorna lista de todos os CHDs (pasta principal + duplicados)."""
    chds = list(PSX.glob("*.chd"))
    if DUP.exists():
        chds.extend(DUP.glob("*.chd"))
    return chds


def make_startup_info():
    """Cria STARTUPINFO com janela oculta (SW_HIDE)."""
    si = subprocess.STARTUPINFO()
    si.dwFlags = STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return si


def test_chd(chd_path, timeout=8, worker_id=0):
    """Testa um CHD no DuckStation headless sem foco.
    Retorna (chd_path, status, detail)."""
    with _duck_log_lock:
        # Limpar log anterior
        if DUCK_LOG_FILE.exists():
            try:
                DUCK_LOG_FILE.unlink()
            except Exception:
                pass

        # Abrir CHD no DuckStation — sem janela, sem foco
        cmd = [DUCK, "-batch", "-nogui", "-fastboot", "-earlyconsole", str(chd_path)]
        si = make_startup_info()
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=si,
                creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
            )
        except Exception as e:
            return (str(chd_path), "FAIL", f"launch_error: {e}")

    # Esperar timeout (fora do lock para permitir paralelismo)
    time.sleep(timeout)

    # Verificar se o processo ainda esta rodando
    poll = proc.poll()
    if poll is not None:
        # Processo terminou antes do timeout
        try:
            stdout = proc.stdout.read().decode("utf-8", errors="replace") if proc.stdout else ""
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        except Exception:
            stdout = stderr = ""
        combined = stdout + stderr
        if poll == 0 and not any(p.lower() in combined.lower() for p in ERROR_PATTERNS):
            return (str(chd_path), "OK", "exited_clean")
        return (str(chd_path), "FAIL", f"exited_{poll}: {combined[:200]}")

    # Processo ainda rodando — matar silenciosamente
    try:
        proc.kill()
        proc.wait(timeout=5)
    except Exception:
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(proc.pid)],
                capture_output=True, timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            pass

    # Ler log do DuckStation
    with _duck_log_lock:
        log_content = ""
        if DUCK_LOG_FILE.exists():
            try:
                log_content = DUCK_LOG_FILE.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    # Verificar erros no log (ignorando warnings benignos)
    log_lower = log_content.lower()
    # Filtrar linhas que sao warnings benignos
    clean_lines = []
    for line in log_content.splitlines():
        line_lower = line.lower()
        if not any(p in line_lower for p in IGNORE_PATTERNS):
            clean_lines.append(line)
    clean_text = "\n".join(clean_lines)
    clean_lower = clean_text.lower()

    for pattern in ERROR_PATTERNS:
        if pattern.lower() in clean_lower:
            for line in clean_lines:
                if pattern.lower() in line.lower():
                    return (str(chd_path), "FAIL", f"log: {line.strip()[:150]}")
            return (str(chd_path), "FAIL", f"log: {pattern}")

    # Verificar indicadores de sucesso (baseado no log real do DuckStation)
    success_indicators = [
        "system booted",      # "System booted in XXXms"
        "boot path:",         # "Boot Path: ..."
        "loading cd image",   # "Loading CD image ..."
        "console region:",    # "Console Region: ..."
        "kernel initialized", # "Kernel initialized."
        " inserting new media", # "Inserting new media..."
    ]
    has_success = any(s in log_lower for s in success_indicators)

    if has_success:
        return (str(chd_path), "OK", "booted")
    else:
        return (str(chd_path), "UNKNOWN", f"no_indicators, log={len(log_content)}")


def worker_test(chd_path, timeout, worker_id):
    try:
        return test_chd(chd_path, timeout, worker_id)
    except Exception as e:
        return (str(chd_path), "FAIL", f"exception: {e}")


def main():
    parser = argparse.ArgumentParser(description="Testa CHDs no DuckStation headless")
    parser.add_argument("--limit", type=int, default=0, help="Limitar numero de CHDs")
    parser.add_argument("--timeout", type=int, default=12, help="Timeout por CHD (segundos)")
    parser.add_argument("--workers", type=int, default=1, help="Instancias paralelas")
    parser.add_argument("--resume", action="store_true", help="Continuar de onde parou")
    args = parser.parse_args()

    log("=" * 60)
    log("DuckStation CHD Tester - Headless (sem foco)")
    log(f"Timeout: {args.timeout}s | Workers: {args.workers}")
    log("=" * 60)

    # Carregar resultados anteriores
    results = {}
    if args.resume and RESULTS_FILE.exists():
        try:
            results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
            log(f"Carregados {len(results)} resultados anteriores")
        except Exception:
            results = {}

    # Obter lista de CHDs
    chds = get_chd_list()
    log(f"Total de CHDs: {len(chds)}")

    # Filtrar ja testados
    to_test = [c for c in chds if str(c) not in results]
    if args.limit > 0:
        to_test = to_test[:args.limit]
    log(f"A testar: {len(to_test)}")

    if not to_test:
        log("Nada a testar!")
        return

    # Garantir que DuckStation nao abre em fullscreen e com audio MUTADO
    if DUCK_SETTINGS.exists():
        try:
            settings = DUCK_SETTINGS.read_text(encoding="utf-8", errors="replace")
            changed = False
            if "Fullscreen = true" in settings:
                settings = settings.replace("Fullscreen = true", "Fullscreen = false")
                changed = True
            if "ShowOSDMessages = true" in settings:
                settings = settings.replace("ShowOSDMessages = true", "ShowOSDMessages = false")
                changed = True
            if "OutputMuted = false" in settings:
                settings = settings.replace("OutputMuted = false", "OutputMuted = true")
                changed = True
            if "LogToConsole = false" in settings:
                settings = settings.replace("LogToConsole = false", "LogToConsole = true")
                changed = True
            if "LogToFile = false" in settings:
                settings = settings.replace("LogToFile = false", "LogToFile = true")
                changed = True
            if changed:
                DUCK_SETTINGS.write_text(settings, encoding="utf-8")
                log("Settings.ini ajustado (fullscreen off, OSD off, audio MUTED, log on)")
        except Exception:
            pass

    ok_count = 0
    fail_count = 0
    unknown_count = 0
    total_deleted = 0
    total_bytes_freed = 0
    start_time = time.time()

    if args.workers == 1:
        for i, chd in enumerate(to_test):
            result = worker_test(chd, args.timeout, 0)
            path, status, detail = result
            results[path] = {"status": status, "detail": detail}
            if status == "OK":
                ok_count += 1
                # Apagar arquivos de origem (BIN/CUE/IMG/ISO) do CHD confirmado
                n_del, bytes_freed = cleanup_source_files(path)
                total_deleted += n_del
                total_bytes_freed += bytes_freed
                if n_del > 0:
                    log(f"  -> Limpou {n_del} arquivos ({bytes_freed/1024/1024:.1f}MB) | Total: {total_deleted} arq, {total_bytes_freed/1024/1024/1024:.1f}GB")
            elif status == "FAIL":
                fail_count += 1
            else:
                unknown_count += 1

            elapsed = time.time() - start_time
            rate = (i + 1) / max(elapsed, 1)
            eta = (len(to_test) - i - 1) / max(rate, 0.01)
            log(f"[{i+1}/{len(to_test)}] {status:>7} | OK={ok_count} FAIL={fail_count} UNK={unknown_count} | ETA={eta/60:.0f}min | del={total_deleted} ({total_bytes_freed/1024/1024/1024:.1f}GB) | {Path(path).name[:40]}")

            if (i + 1) % 10 == 0:
                try:
                    RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
                except Exception:
                    pass
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for i, chd in enumerate(to_test):
                f = executor.submit(worker_test, chd, args.timeout, i % args.workers)
                futures[f] = chd

            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                path, status, detail = result
                results[path] = {"status": status, "detail": detail}
                if status == "OK":
                    ok_count += 1
                elif status == "FAIL":
                    fail_count += 1
                else:
                    unknown_count += 1

                elapsed = time.time() - start_time
                done = i + 1
                rate = done / max(elapsed, 1)
                eta = (len(to_test) - done) / max(rate, 0.01)
                log(f"[{done}/{len(to_test)}] {status:>7} | OK={ok_count} FAIL={fail_count} UNK={unknown_count} | ETA={eta/60:.0f}min | {Path(path).name[:50]}")

                if done % 10 == 0:
                    try:
                        RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
                    except Exception:
                        pass

    # Salvar resultados finais
    try:
        RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"Erro ao salvar resultados: {e}")

    # Relatorio
    log("=" * 60)
    log("TESTE COMPLETO")
    log(f"  Total:       {len(to_test)}")
    log(f"  OK:          {ok_count}")
    log(f"  FAIL:        {fail_count}")
    log(f"  UNKNOWN:     {unknown_count}")
    log(f"  Apagados:    {total_deleted} arquivos")
    log(f"  Espaco livre: {total_bytes_freed/1024/1024/1024:.1f} GB")
    log(f"  Tempo:       {(time.time()-start_time)/60:.1f}min")
    log("=" * 60)

    if fail_count > 0:
        log("\nFalhas:")
        for path, info in results.items():
            if info["status"] == "FAIL":
                log(f"  {Path(path).name}: {info['detail'][:100]}")


if __name__ == "__main__":
    main()
