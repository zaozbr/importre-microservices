"""
importre_supervisor.py — Watchdog autonomo para o importre.py

Monitora continuamente:
1. Processo importre.py ativo (reinicia se morrer)
2. Servidor HTTP respondendo (reinicia se travar)
3. Progresso de downloads (reinicia se estagnar >10min)
4. Multiplas instancias (mata duplicatas)
5. Itens presos em in_progress (drena)
6. Retry_count acumulado (reseta periodicamente)
7. Sites desativados por fail_count (reativa archive_org)

Rodar em background:
    python importre_supervisor.py
    Start-Process python -ArgumentList "importre_supervisor.py" -WindowStyle Hidden
"""
import os
import sys
import json
import time
import logging
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timedelta
import requests

# ============================================================
# CONFIG
# ============================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
QUEUE_PATH = STATE_DIR / "queue.json"
LOG_PATH = STATE_DIR / "importre.log"
SUP_LOG_PATH = STATE_DIR / "supervisor.log"
IMPORTRE_SCRIPT = SCRIPT_DIR / "importre.py"
SERVER_SCRIPT = SCRIPT_DIR / "importre_server.py"
LOCK_PATH = STATE_DIR / "importre.lock"
PID_FILE = STATE_DIR / "importre.pid"

SERVER_URL = "http://127.0.0.1:8765"
CHECK_INTERVAL = 30          # checar a cada 30s (mais rapido para detectar estagnacao)
STALE_THRESHOLD = 300        # 5 min sem progresso = reiniciar
STALE_ITEM_THRESHOLD = 300   # 5 min item preso em in_progress = drenar (60s era muito agressivo)
MAX_RETRIES_RESET = 200      # resetar retry_count quando acumular demais
WORKERS = 8  # 8 workers — 60 causava 105+ processos e lockup do sistema
ROUNDS = 999
LIMIT = 999

# ============================================================
# LOGGING
# ============================================================
class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler que nao quebra se stdout/stderr estiver fechado/invalido."""
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
log = logging.getLogger("supervisor")

# ============================================================
# UTILS
# ============================================================
def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}

def save_json(path, data):
    try:
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.error(f"Erro ao salvar {path}: {e}")

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


def _list_python_processes():
    """Helper: retorna lista de dicts {pid, cmdline} para python.exe via psutil."""
    try:
        import psutil
        out = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info.get("name", "").lower() != "python.exe":
                    continue
                cmd = proc.info.get("cmdline") or []
                out.append({"pid": proc.info["pid"], "cmdline": " ".join(cmd)})
            except Exception:
                pass
        return out
    except Exception as e:
        log.error(f"Erro ao listar processos via psutil: {e}")
        return []


def get_importre_processes():
    """Retorna lista de PIDs do processo orquestrador importre.py (excluindo supervisor, server e --task)."""
    results = []
    for p in _list_python_processes():
        cmd = p["cmdline"]
        if "importre.py" not in cmd:
            continue
        if any(x in cmd for x in ["supervisor", "importre_server", "--task", "--role"]):
            continue
        results.append((p["pid"], cmd))
    return results


def get_task_processes():
    """Retorna lista de PIDs de processos --task (search e download)."""
    results = []
    for p in _list_python_processes():
        if "--task" in p["cmdline"]:
            results.append((p["pid"], p["cmdline"]))
    return results


def get_server_processes():
    """Retorna lista de PIDs de processos importre_server.py."""
    results = []
    for p in _list_python_processes():
        if "importre_server" in p["cmdline"]:
            results.append(p["pid"])
    return results

def kill_pid(pid):
    try:
        kwargs = get_run_kwargs(timeout=10)
        # get_run_kwargs já inclui capture_output, não duplicar
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], **kwargs)
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


def start_importre():
    """Inicia importre.py em background."""
    try:
        # Usar pythonw.exe se disponivel para evitar console visivel
        python_exe = sys.executable
        if python_exe.lower().endswith("python.exe"):
            pythonw = python_exe[:-10] + "pythonw.exe"
            if Path(pythonw).exists():
                python_exe = pythonw
        cmd = [python_exe, str(IMPORTRE_SCRIPT), "--workers", str(WORKERS), "--rounds", str(ROUNDS), "--limit", str(LIMIT)]
        proc = subprocess.Popen(cmd, **get_no_window_kwargs())
        log.info(f"importre.py iniciado (PID {proc.pid})")
        return proc.pid
    except Exception as e:
        log.error(f"Erro ao iniciar importre.py: {e}")
        return None

def check_server():
    """Verifica se servidor HTTP responde. Retorna (ok, status_dict)."""
    try:
        resp = requests.get(f"{SERVER_URL}/api/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return True, data.get("status", {})
    except Exception:
        pass
    return False, None

def check_log_activity():
    """Verifica se o log tem atividade recente (ultima linha nos ultimos 5 min)."""
    try:
        if not LOG_PATH.exists():
            return False
        mtime = datetime.fromtimestamp(LOG_PATH.stat().st_mtime)
        age = (datetime.now() - mtime).total_seconds()
        return age < 300  # log modificado nos ultimos 5 min
    except Exception:
        return False

def drain_stale_items():
    """Drena itens presos em in_progress ha mais de STALE_ITEM_THRESHOLD segundos."""
    try:
        data = load_json(QUEUE_PATH)
        if not data:
            return 0
        in_prog = data.get("in_progress", {})
        if not in_prog:
            return 0
        now = datetime.now()
        returned = 0
        for serial in list(in_prog.keys()):
            item = in_prog[serial]
            item_time = item.get("_started_at")
            if item_time:
                try:
                    dt = datetime.fromisoformat(item_time)
                    age = (now - dt).total_seconds()
                    if age > STALE_ITEM_THRESHOLD:
                        log.warning(f"Item preso {serial} ha {int(age)}s — devolvendo para fila")
                        item.pop("_phase", None)
                        item.pop("_current_site", None)
                        item.pop("_detail", None)
                        item.pop("_worker", None)
                        item.pop("_started_at", None)
                        data["queue"].append(item)
                        del in_prog[serial]
                        returned += 1
                except Exception:
                    pass
            elif not item.get("_worker"):
                # Item sem worker — preso
                log.warning(f"Item {serial} sem _worker — devolvendo para fila")
                item.pop("_phase", None)
                item.pop("_current_site", None)
                item.pop("_detail", None)
                item.pop("_started_at", None)
                data["queue"].append(item)
                del in_prog[serial]
                returned += 1
        if returned > 0:
            save_json(QUEUE_PATH, data)
            log.info(f"Drenados {returned} itens presos")
        return returned
    except Exception as e:
        log.error(f"Erro ao drenar itens: {e}")
        return 0

def reset_retry_counts():
    """Reseta retry_count se acumular demais."""
    try:
        data = load_json(QUEUE_PATH)
        if not data:
            return
        rc = data.get("retry_count", {})
        if len(rc) > MAX_RETRIES_RESET:
            log.info(f"Resetando {len(rc)} retry_counts acumulados")
            data["retry_count"] = {}
            save_json(QUEUE_PATH, data)
    except Exception as e:
        log.error(f"Erro ao resetar retries: {e}")

def reenable_archive_org():
    """Reativa archive_org se foi desativado por fail_count."""
    try:
        sites_path = STATE_DIR / "sites.json"
        sites = load_json(sites_path)
        if not sites:
            return
        changed = False
        for name in ["archive_org", "archive_org_jp"]:
            if name in sites:
                s = sites[name]
                # Nao reativar se usuario desativou propositalmente
                if s.get("user_disabled"):
                    continue
                if not s.get("enabled", False) and s.get("fail_count", 0) < s.get("max_fails", 50):
                    s["enabled"] = True
                    changed = True
                    log.info(f"{name} reativado (fail_count={s.get('fail_count', 0)})")
        if changed:
            save_json(sites_path, sites)
    except Exception as e:
        log.error(f"Erro ao reativar sites: {e}")

def cleanup_pycache():
    """Remove __pycache__ para evitar cache antigo."""
    try:
        pycache = SCRIPT_DIR / "__pycache__"
        if pycache.exists():
            import shutil
            shutil.rmtree(pycache, ignore_errors=True)
    except Exception:
        pass

# ============================================================
# SUPERVISOR PRINCIPAL
# ============================================================
def supervisor_loop():
    log.info("=" * 60)
    log.info("Supervisor iniciado")
    log.info(f"  Script: {IMPORTRE_SCRIPT}")
    log.info(f"  Estado: {STATE_DIR}")
    log.info(f"  Check interval: {CHECK_INTERVAL}s")
    log.info(f"  Stale threshold: {STALE_THRESHOLD}s ({STALE_THRESHOLD//60}min)")
    log.info("=" * 60)

    last_completed = 0
    last_progress_time = datetime.now()
    restart_count = 0
    consecutive_failures = 0

    # Inicio imediato: garantir que importre.py esteja rodando
    cleanup_pycache()
    drain_stale_items()
    start_importre()
    time.sleep(10)

    while True:
        try:
            now = datetime.now()

            # 1. Verificar processos importre.py
            procs = get_importre_processes()
            n_procs = len(procs)

            # 2. Verificar servidor HTTP
            server_ok, status = check_server()

            # 3. Verificar progresso
            current_completed = status.get("completed", 0) if status else 0
            in_progress = status.get("in_progress", 0) if status else 0
            pending = status.get("pending", 0) if status else 0

            if current_completed > last_completed:
                last_completed = current_completed
                last_progress_time = now
                consecutive_failures = 0
            else:
                # Sem progresso
                stale_secs = (now - last_progress_time).total_seconds()
                # Se esta idle (in_progress == 0) com pending > 0, reiniciar mais rapido
                # Mas se ha failed items (fase retry), dar mais tempo (retries via Google sao lentos)
                failed_count = len(status.get("failed_items", {})) if status else 0
                if in_progress == 0 and pending > 0:
                    idle_threshold = 300
                elif in_progress == 0 and pending == 0 and failed_count > 0:
                    idle_threshold = 900  # 15 min — retries via Google sao lentos
                else:
                    idle_threshold = STALE_THRESHOLD
                if stale_secs > idle_threshold:
                    log.warning(f"Sem progresso ha {int(stale_secs)}s (idle={in_progress==0}, pend={pending}, failed={failed_count}) — reiniciando")
                    # Matar todos os processos importre
                    for pid, _ in procs:
                        kill_pid(pid)
                    time.sleep(3)
                    cleanup_pycache()
                    drain_stale_items()
                    reset_retry_counts()
                    time.sleep(2)
                    start_importre()
                    restart_count += 1
                    consecutive_failures += 1
                    last_progress_time = now  # reset timer
                    time.sleep(CHECK_INTERVAL)
                    continue

            # 4. Matar instancias duplicadas do ORQUESTRADOR (manter apenas 1)
            #    --task processes NAO sao duplicatas — sao subprocessos legitimos
            if n_procs > 1:
                log.warning(f"{n_procs} orquestradores importre.py — matando duplicatas")
                # Manter o primeiro (mais antigo), matar o resto
                for pid, _ in procs[1:]:
                    kill_pid(pid)
                time.sleep(3)

            # 4b. Matar instancias duplicadas do SERVIDOR HTTP (manter apenas 1)
            server_procs = get_server_processes()
            if len(server_procs) > 1:
                log.warning(f"{len(server_procs)} servidores importre_server.py — matando duplicatas")
                for pid in server_procs[1:]:
                    kill_pid(pid)
                time.sleep(3)

            # 5. Se nao tem orquestrador, iniciar
            if n_procs == 0:
                log.warning("importre.py nao esta rodando — iniciando")
                cleanup_pycache()
                drain_stale_items()
                time.sleep(2)
                start_importre()
                restart_count += 1
                last_progress_time = now
                time.sleep(CHECK_INTERVAL)
                continue

            # 5b. Verificar se o orquestrador esta lancando --task processes
            #     NOTA: importre.py usa ThreadPoolExecutor (threads internas), NAO subprocessos --task.
            #     "0 tasks" é NORMAL e NÃO indica problema. Só reiniciar se sem progresso real.
            #     O check de progresso real já é feito acima (stale_secs > idle_threshold).
            #     Este bloco foi desativado para evitar reinicios desnecessários.
            # task_procs = get_task_processes()
            # n_tasks = len(task_procs)
            # if n_procs > 0 and n_tasks == 0 and pending > 0:
            #     idle_secs = (now - last_progress_time).total_seconds()
            #     if idle_secs > 120:
            #         log.warning(f"Orquestrador ativo mas 0 tasks ha {int(idle_secs)}s — reiniciando")
            #         for pid, _ in procs:
            #             kill_pid(pid)
            #         time.sleep(3)
            #         cleanup_pycache()
            #         drain_stale_items()
            #         time.sleep(2)
            #         start_importre()
            #         restart_count += 1
            #         last_progress_time = now
            #         time.sleep(CHECK_INTERVAL)
            #         continue

            # 6. Se servidor nao responde mas processo esta ativo
            if not server_ok and n_procs > 0:
                log.warning("Servidor HTTP nao responde — verificando log")
                log_active = check_log_activity()
                if not log_active:
                    log.warning("Log sem atividade recente — reiniciando processo")
                    for pid, _ in procs:
                        kill_pid(pid)
                    time.sleep(3)
                    cleanup_pycache()
                    drain_stale_items()
                    time.sleep(2)
                    start_importre()
                    restart_count += 1
                    last_progress_time = now
                    time.sleep(CHECK_INTERVAL)
                    continue

            # 7. Drenar itens presos periodicamente
            drain_stale_items()

            # 8. Resetar retry_count se acumular demais
            reset_retry_counts()

            # 9. Reativar archive_org se desativado indevidamente
            reenable_archive_org()

            # 10. Log de status
            n_tasks = 0  # importre usa threads, não subprocessos --task
            if server_ok:
                log.info(f"OK: {current_completed} | Pend: {pending} | EmAnd: {in_progress} | "
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
             "Get-WmiObject Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*importre_supervisor*' } | "
             "Select-Object ProcessId | ConvertTo-Json"],
            **get_run_kwargs(10)
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, list):
                pids = [int(d["ProcessId"]) for d in data]
            else:
                pids = [int(data["ProcessId"])]
            # Se ja tem supervisor rodando (e nao sou eu), nao iniciar outro
            my_pid = os.getpid()
            other_pids = [p for p in pids if p != my_pid]
            if other_pids:
                print(f"Supervisor ja rodando (PID {other_pids[0]}) — saindo")
                sys.exit(0)
    except Exception:
        pass

    supervisor_loop()
