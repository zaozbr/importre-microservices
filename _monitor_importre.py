"""Monitor autonomo do importre.
Roda em loop, verifica saude do sistema, reinicia processos mortos,
drena itens presos, reativa sites desativados e loga estado.
Uso: python _monitor_importre.py
"""
import os
import sys
import json
import time
import subprocess
import re
import requests
from pathlib import Path
from datetime import datetime, timedelta

PSX_DIR = Path(r"D:\roms\library\roms\psx")
STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
QUEUE_PATH = STATE_DIR / "queue.json"
SITES_PATH = STATE_DIR / "sites.json"
SUPERVISOR_LOG = STATE_DIR / "supervisor.log"
MONITOR_LOG = STATE_DIR / "monitor.log"
IMPORTRE_URL = "http://127.0.0.1:8765"
CHD_URL = "http://127.0.0.1:8766"

CHECK_INTERVAL = 60          # checar a cada 60s
STALE_ITEM_THRESHOLD = 600   # 10 min preso = drenar
STALE_PROGRESS_THRESHOLD = 600  # 10 min sem progresso = reiniciar importre


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [MONITOR] {msg}"
    try:
        with open(MONITOR_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        print(line, flush=True)
    except OSError:
        pass


def get_pids(pattern):
    """Lista PIDs de processos python.exe cujo CommandLine contenha pattern (sem PowerShell).
    Exclui o proprio processo para evitar auto-match.
    """
    try:
        import psutil
        own_pid = os.getpid()
        pids = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info.get("pid") == own_pid:
                    continue
                if proc.info.get("name", "").lower() != "python.exe":
                    continue
                cmdline = " ".join(proc.info.get("cmdline") or [])
                if pattern in cmdline:
                    pids.append(proc.info["pid"])
            except Exception:
                pass
        return pids
    except Exception as e:
        log(f"Erro ao listar {pattern} via psutil: {e}")
        return []


def safe_run(cmd, **kwargs):
    """Executa subprocess.run sem disparar OSError se stdout estiver fechado."""
    if sys.platform == "win32":
        if "startupinfo" not in kwargs:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = si
        if "creationflags" not in kwargs:
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        return subprocess.run(cmd, **kwargs)
    except OSError as e:
        # Se stdout/stderr estiver invalido, redirecionar para DEVNULL e tentar novamente
        try:
            kwargs.setdefault("stdout", subprocess.DEVNULL)
            kwargs.setdefault("stderr", subprocess.DEVNULL)
            return subprocess.run(cmd, **kwargs)
        except Exception:
            return None
    except Exception:
        return None


def kill_pid(pid):
    try:
        safe_run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=10)
        log(f"PID {pid} morto")
    except Exception as e:
        log(f"Erro ao matar PID {pid}: {e}")


def start_process(script_name, args=None, no_window=True):
    try:
        log(f"Iniciando {script_name}...")
        # Usar pythonw.exe se disponivel para nao abrir console
        python_exe = sys.executable
        if python_exe.lower().endswith("python.exe"):
            pythonw = python_exe[:-10] + "pythonw.exe"
            if Path(pythonw).exists():
                python_exe = pythonw
        cmd = [python_exe, str(PSX_DIR / script_name)]
        if args:
            cmd += args
        kwargs = {}
        if sys.platform == "win32" and no_window:
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
        kwargs.setdefault("stdout", subprocess.DEVNULL)
        kwargs.setdefault("stderr", subprocess.DEVNULL)
        try:
            proc = subprocess.Popen(cmd, **kwargs)
        except OSError as e:
            log(f"OSError ao iniciar {script_name}: {e}, tentando com DEVNULL forcado")
            kwargs["stdout"] = subprocess.DEVNULL
            kwargs["stderr"] = subprocess.DEVNULL
            proc = subprocess.Popen(cmd, **kwargs)
        log(f"{script_name} iniciado (PID {proc.pid})")
        return proc.pid
    except Exception as e:
        log(f"Erro ao iniciar {script_name}: {e}")
        return None


def check_server(url, timeout=10):
    try:
        resp = requests.get(f"{url}/api/status", timeout=timeout)
        return resp.status_code == 200, resp.json() if resp.status_code == 200 else None
    except Exception as e:
        return False, str(e)


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def save_json(path, data):
    try:
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log(f"Erro ao salvar {path}: {e}")


def drain_stale_items():
    """Devolve para fila itens presos em in_progress ha mais de STALE_ITEM_THRESHOLD."""
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
                    log(f"Item preso {serial} ha {int(age)}s — devolvendo para fila")
                    for key in ["_phase", "_current_site", "_detail", "_worker", "_started_at"]:
                        item.pop(key, None)
                    data["queue"].append(item)
                    del in_prog[serial]
                    returned += 1
            except Exception:
                pass
        elif not item.get("_worker"):
            log(f"Item {serial} sem _worker — devolvendo para fila")
            for key in ["_phase", "_current_site", "_detail", "_worker", "_started_at"]:
                item.pop(key, None)
            data["queue"].append(item)
            del in_prog[serial]
            returned += 1
    if returned:
        save_json(QUEUE_PATH, data)
    return returned


def reactivate_sites():
    """Reativa sites desativados por fail_count (exceto blacklist)."""
    sites = load_json(SITES_PATH, {})
    changed = False
    for key, site in sites.items():
        if not site.get("enabled") and site.get("fail_count", 0) > 0:
            site["enabled"] = True
            site["fail_count"] = 0
            log(f"Site {key} reativado pelo monitor")
            changed = True
    if changed:
        save_json(SITES_PATH, sites)


def get_last_completed():
    """Retorna numero de completados e timestamp do log do supervisor."""
    try:
        data = load_json(QUEUE_PATH)
        return len(data.get("completed", {}))
    except Exception:
        return 0


def monitor_loop():
    log("=== Monitor do importre iniciado ===")
    last_completed = get_last_completed()
    last_progress_time = time.time()

    while True:
        try:
            now = time.time()

            log("Ciclo iniciado")

            # 1) Verificar supervisores
            sup_pids = get_pids("importre_supervisor.py")
            log(f"Supervisores importre: {sup_pids}")
            if not sup_pids:
                log("Supervisor importre nao encontrado — reiniciando")
                start_process("importre_supervisor.py")
            elif len(sup_pids) > 1:
                log(f"{len(sup_pids)} supervisores importre — matando os mais antigos")
                for pid in sup_pids[:-1]:
                    kill_pid(pid)

            chd_sup_pids = get_pids("_chd_supervisor.py")
            log(f"Supervisores CHD: {chd_sup_pids}")
            if not chd_sup_pids:
                log("Supervisor CHD nao encontrado — reiniciando")
                start_process("_chd_supervisor.py")
            elif len(chd_sup_pids) > 1:
                log(f"{len(chd_sup_pids)} supervisores CHD — matando os mais antigos")
                for pid in chd_sup_pids[:-1]:
                    kill_pid(pid)

            # 2) Verificar importre.py principal
            main_pids = get_main_importre_pids()
            log(f"Importre principais: {main_pids}")
            if not main_pids:
                log("importre.py principal nao encontrado — aguardando supervisor reiniciar")
            elif len(main_pids) > 1:
                log(f"{len(main_pids)} importre.py principais — matando os mais antigos")
                for pid in main_pids[:-1]:
                    kill_pid(pid)

            # 3) Verificar servidor HTTP
            log("Verificando servidor HTTP...")
            ok, status = check_server(IMPORTRE_URL)
            if not ok:
                log(f"Servidor importre nao responde: {status}")
            else:
                pending = status.get("status", {}).get("pending", 0)
                in_progress = status.get("status", {}).get("in_progress", 0)
                completed = status.get("status", {}).get("completed", 0)
                failed = status.get("status", {}).get("failed", 0)
                log(f"Status: pending={pending} in_progress={in_progress} completed={completed} failed={failed}")

                if completed > last_completed:
                    last_completed = completed
                    last_progress_time = now
                elif now - last_progress_time > STALE_PROGRESS_THRESHOLD:
                    log(f"Sem progresso ha {int(now - last_progress_time)}s — reiniciando importre")
                    if main_pids:
                        for pid in main_pids:
                            kill_pid(pid)
                    last_progress_time = now

            # 4) Drenar itens presos
            drained = drain_stale_items()
            if drained:
                log(f"{drained} itens drenados de in_progress")

            # 5) Reativar sites desativados
            reactivate_sites()

            # 6) Verificar duplicatas CHD converter
            chd_pids = get_pids("_chd_convert_v2.py")
            if len(chd_pids) > 1:
                log(f"{len(chd_pids)} conversores CHD — matando os mais antigos")
                for pid in chd_pids[:-1]:
                    kill_pid(pid)

            # 7) Verificar duplicatas do servidor HTTP
            server_pids = get_pids("importre_server.py")
            if len(server_pids) > 1:
                log(f"{len(server_pids)} servidores HTTP — matando os mais antigos")
                for pid in server_pids[:-1]:
                    kill_pid(pid)

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            log(f"Erro no monitor loop: {e}")
            time.sleep(10)


def get_main_importre_pids():
    """Lista PIDs do importre.py principal (sem PowerShell)."""
    try:
        import psutil
        pids = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info.get("name", "").lower() != "python.exe":
                    continue
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "importre.py" not in cmd:
                    continue
                if any(x in cmd for x in ["supervisor", "importre_server", "--task", "--role"]):
                    continue
                pids.append(proc.info["pid"])
            except Exception:
                pass
        return pids
    except Exception as e:
        log(f"Erro ao listar importre main via psutil: {e}")
        return []


if __name__ == "__main__":
    monitor_loop()
