"""
_chd_supervisor.py — Watchdog autonomo para o conversor CHD (_chd_convert_v2.py)

Monitora continuamente:
1. Processo _chd_convert_v2.py ativo (reinicia se morrer)
2. Dashboard HTTP em http://127.0.0.1:8766 respondendo (reinicia se travar)
3. Progresso de conversao (reinicia se estagnar >10min)
4. Multiplas instancias (mata duplicatas)
5. Log recente (reinicia se log nao for atualizado e servidor nao responder)

Regras criticas:
- NUNCA usar taskkill /F /IM chdman.exe (o importre tambem usa chdman)
- Matar apenas processos python _chd_convert_v2.py por PID especifico

Rodar em background:
    python _chd_supervisor.py
    Start-Process python -ArgumentList "_chd_supervisor.py" -WindowStyle Hidden
"""
import os
import sys
import json
import time
import logging
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
CHD_SCRIPT = SCRIPT_DIR / "_chd_convert_v2.py"
LOG_PATH = SCRIPT_DIR / "_chd_convert.log"
PROGRESS_PATH = SCRIPT_DIR / "_chd_convert_progress.json"
LOCK_PATH = SCRIPT_DIR / "_chd_convert.lock"
SUP_LOG_PATH = SCRIPT_DIR / "_chd_supervisor.log"
PID_FILE = SCRIPT_DIR / "_chd_supervisor.pid"

SERVER_URL = "http://127.0.0.1:8766"
CHECK_INTERVAL = 60          # checar a cada 60s
STALE_THRESHOLD = 600        # 10 min sem progresso = reiniciar
LOG_IDLE_THRESHOLD = 300     # 5 min sem log novo + servidor offline = reiniciar
WORKERS = 4

# ============================================================
# LOGGING
# ============================================================
class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            super().emit(record)
        except OSError:
            pass

    def flush(self):
        try:
            super().flush()
        except OSError:
            pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(SUP_LOG_PATH, encoding="utf-8"),
        SafeStreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("chd_supervisor")

# ============================================================
# UTILS
# ============================================================
def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def save_pid():
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass


def notify_user(title, message):
    """Notificacoes toast desativadas para nao abrir janelas/popups."""
    pass


def get_run_kwargs(timeout=None):
    """Kwargs para subprocess.run sem abrir janela no Windows."""
    kwargs = {"capture_output": True, "text": True}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_BREAKAWAY_FROM_JOB
        )
    return kwargs


def get_chd_processes():
    """Retorna lista de PIDs do orquestrador _chd_convert_v2.py (excluindo supervisor)."""
    try:
        import psutil
        results = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info.get("name", "").lower() not in ("python.exe", "pythonw.exe"):
                    continue
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "_chd_convert_v2.py" in cmd and "supervisor" not in cmd:
                    results.append((proc.info["pid"], cmd))
            except Exception:
                pass
        return results
    except Exception as e:
        log.error(f"Erro ao listar processos CHD via psutil: {e}")
        return []


def kill_pid(pid):
    """Mata processo por PID. NUNCA mata chdman.exe globalmente."""
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], timeout=10, **get_run_kwargs())
        log.info(f"PID {pid} morto")
    except Exception as e:
        log.warning(f"Erro ao matar PID {pid}: {e}")


def get_no_window_kwargs():
    """Retorna kwargs para subprocess.Popen/run sem janela e sem roubar foco no Windows."""
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
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


def start_chd_converter():
    """Inicia _chd_convert_v2.py em background."""
    try:
        # Usar pythonw.exe se disponivel para evitar console visivel
        python_exe = sys.executable
        if python_exe.lower().endswith("python.exe"):
            pythonw = python_exe[:-10] + "pythonw.exe"
            if Path(pythonw).exists():
                python_exe = pythonw
        cmd = [python_exe, str(CHD_SCRIPT), "--workers", str(WORKERS)]
        proc = subprocess.Popen(cmd, **get_no_window_kwargs())
        log.info(f"_chd_convert_v2.py iniciado (PID {proc.pid})")
        return proc.pid
    except Exception as e:
        log.error(f"Erro ao iniciar _chd_convert_v2.py: {e}")
        return None


def check_server():
    """Verifica se dashboard HTTP responde. Retorna (ok, status_dict)."""
    try:
        req = urllib.request.Request(f"{SERVER_URL}/api/status", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return True, json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        pass
    return False, None


def check_log_activity():
    """Verifica se o log tem atividade recente."""
    try:
        if not LOG_PATH.exists():
            return False
        mtime = datetime.fromtimestamp(LOG_PATH.stat().st_mtime)
        age = (datetime.now() - mtime).total_seconds()
        return age < LOG_IDLE_THRESHOLD
    except Exception:
        return False


def cleanup_lock():
    """Remove lock file antigo se o processo dono nao existe mais."""
    try:
        if not LOCK_PATH.exists():
            return
        text = LOCK_PATH.read_text(encoding="utf-8").strip()
        pid = int(text)
        if pid == os.getpid():
            return
        try:
            import psutil
            p = psutil.Process(pid)
            cmd = " ".join(p.cmdline() or [])
            if "_chd_convert_v2.py" in cmd and p.is_running():
                return
        except Exception:
            pass
        LOCK_PATH.unlink()
        log.info(f"Lock antigo (PID {pid}) removido")
    except Exception:
        pass


def supervisor_loop():
    log.info("=== CHD Supervisor iniciado ===")
    log.info(f"Monitorando: {SERVER_URL}")
    log.info(f"Log do conversor: {LOG_PATH}")
    save_pid()

    last_done = -1
    last_progress_time = datetime.now()
    restart_count = 0
    consecutive_failures = 0

    while True:
        now = datetime.now()
        log.debug("Iniciando ciclo de checagem")
        try:
            # 1. Verificar processos _chd_convert_v2.py
            procs = get_chd_processes()
            n_procs = len(procs)

            # 2. Verificar servidor HTTP
            server_ok, status = check_server()

            # 3. Verificar progresso (considera completed + failed + skipped)
            current_completed = 0
            current_failed = 0
            current_skipped = 0
            if status and isinstance(status, dict):
                current_completed = int(status.get("completed", 0))
                current_failed = int(status.get("failed", 0))
                current_skipped = int(status.get("skipped", 0))
            else:
                progress = load_json(PROGRESS_PATH, {})
                current_completed = int(progress.get("completed", 0))
                current_failed = int(progress.get("failed", 0))
                current_skipped = int(progress.get("skipped", 0))

            current_done = current_completed + current_failed + current_skipped
            in_progress = status.get("in_progress", {}) if status else {}
            n_in_progress = len(in_progress) if isinstance(in_progress, dict) else 0
            total = status.get("total", 0) if status else progress.get("total", 0)

            if current_done > last_done:
                last_done = current_done
                last_progress_time = now
                consecutive_failures = 0
            else:
                stale_secs = (now - last_progress_time).total_seconds()
                if stale_secs > STALE_THRESHOLD:
                    reason = "servidor offline"
                    if not server_ok:
                        log.warning(f"Sem progresso ha {int(stale_secs)}s e servidor offline — reiniciando")
                    elif n_in_progress == 0 and total > 0:
                        reason = "nenhum item em progresso"
                        log.warning(f"Sem progresso ha {int(stale_secs)}s e nenhum item em progresso — reiniciando")
                    else:
                        reason = f"{n_in_progress} itens travados"
                        log.warning(f"Sem progresso ha {int(stale_secs)}s com {n_in_progress} itens travados — reiniciando")
                    notify_user("CHD Supervisor", f"Reiniciando conversor ({reason})")
                    for pid, _ in procs:
                        kill_pid(pid)
                    time.sleep(3)
                    cleanup_lock()
                    time.sleep(2)
                    start_chd_converter()
                    restart_count += 1
                    consecutive_failures += 1
                    last_progress_time = now
                    time.sleep(CHECK_INTERVAL)
                    continue

            # 4. Matar instancias duplicadas do orquestrador
            if n_procs > 1:
                log.warning(f"{n_procs} orquestradores _chd_convert_v2.py — matando duplicatas")
                notify_user("CHD Supervisor", f"{n_procs} instancias do conversor — matando duplicatas")
                for pid, _ in procs[1:]:
                    kill_pid(pid)
                time.sleep(3)

            # 5. Se nao tem orquestrador, iniciar
            if n_procs == 0:
                log.warning("_chd_convert_v2.py nao esta rodando — iniciando")
                notify_user("CHD Supervisor", "Conversor CHD parado — reiniciando automaticamente")
                cleanup_lock()
                time.sleep(2)
                start_chd_converter()
                restart_count += 1
                last_progress_time = now
                time.sleep(CHECK_INTERVAL)
                continue

            # 6. Se servidor nao responde mas processo esta ativo
            if not server_ok and n_procs > 0:
                log_active = check_log_activity()
                if not log_active:
                    log.warning("Servidor HTTP offline e log sem atividade recente — reiniciando")
                    for pid, _ in procs:
                        kill_pid(pid)
                    time.sleep(3)
                    cleanup_lock()
                    time.sleep(2)
                    start_chd_converter()
                    restart_count += 1
                    consecutive_failures += 1
                    last_progress_time = now
                    time.sleep(CHECK_INTERVAL)
                    continue
                else:
                    log.warning("Servidor HTTP offline, mas log ainda ativo — aguardando")

            # 7. Log de status
            if server_ok:
                log.info(f"OK: {current_completed}/{total} | EmAnd: {n_in_progress} | "
                         f"Orch: {n_procs} | Restarts: {restart_count} | "
                         f"Stale: {int((now - last_progress_time).total_seconds())}s")
            else:
                log.warning(f"Servidor offline | Orch: {n_procs} | Restarts: {restart_count}")

            # Backoff exponencial se muitas falhas consecutivas
            sleep_time = CHECK_INTERVAL
            if consecutive_failures >= 3:
                sleep_time = CHECK_INTERVAL * (consecutive_failures - 1)
                log.warning(f"{consecutive_failures} falhas consecutivas — esperando {sleep_time}s")
                if consecutive_failures > 10:
                    log.error("Muitas falhas consecutivas — parando por 10min")
                    time.sleep(600)
                    consecutive_failures = 0
                    continue

            time.sleep(sleep_time)

        except KeyboardInterrupt:
            log.info("Supervisor interrompido pelo usuario")
            break
        except Exception as e:
            log.error(f"Erro no loop do supervisor: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    # Verificar se ja existe um supervisor rodando
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-WmiObject Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | "
             "Where-Object { $_.CommandLine -like '*_chd_supervisor.py*' } | "
             "Select-Object ProcessId | ConvertTo-Json"],
            **get_run_kwargs(10)
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, list):
                pids = [int(d["ProcessId"]) for d in data]
            else:
                pids = [int(data["ProcessId"])]
            my_pid = os.getpid()
            other_pids = [p for p in pids if p != my_pid]
            if other_pids:
                print(f"Supervisor CHD ja rodando (PID {other_pids[0]}) — saindo")
                sys.exit(0)
    except Exception:
        pass

    supervisor_loop()
