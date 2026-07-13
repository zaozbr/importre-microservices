"""
Watchdog MINIMAL para importre.py — nunca morre, apenas garante 1 processo rodando.
Detecta travamento via log file inativo (>10 min).
"""
import os
import subprocess
import sys
import time
from datetime import datetime

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

PSX_DIR = r"D:\roms\library\roms\psx"
PYTHON = sys.executable
CHECK_INTERVAL = 30
LOG_PATH = os.path.join(PSX_DIR, "..", "_importre_state", "importre.log")
STALE_LOG_THRESHOLD = 600  # 10 min sem log = travado


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [WD] {msg}"
    print(line, flush=True)


def find_importre_pids():
    pids = []
    if HAS_PSUTIL:
        for p in psutil.process_iter(['pid', 'cmdline']):
            try:
                cl = ' '.join(p.info['cmdline'] or [])
                ll = cl.lower()
                if 'importre.py' in ll and 'importre_server' not in ll \
                   and 'importre_supervisor' not in ll and 'watchdog' not in ll:
                    pids.append(p.info['pid'])
            except Exception:
                pass
    return pids


def find_server_pids():
    pids = []
    if HAS_PSUTIL:
        for p in psutil.process_iter(['pid', 'cmdline']):
            try:
                cl = ' '.join(p.info['cmdline'] or [])
                ll = cl.lower()
                if 'importre_server.py' in ll and 'watchdog' not in ll:
                    pids.append(p.info['pid'])
            except Exception:
                pass
    return pids


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


def start_server():
    cmd = [PYTHON, "importre_server.py"]
    try:
        proc = subprocess.Popen(cmd, cwd=PSX_DIR, close_fds=True, **get_no_window_kwargs())
        log(f"importre_server.py iniciado PID={proc.pid}")
        return proc.pid
    except Exception as e:
        log(f"Erro ao iniciar servidor: {e}")
        return None


def kill_pid(pid):
    if HAS_PSUTIL:
        try:
            psutil.Process(pid).kill()
            return
        except Exception:
            pass
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], timeout=10)
    except Exception:
        pass


def start_importre():
    cmd = [PYTHON, "importre.py", "--workers", "8", "--rounds", "999", "--limit", "999", "--no-server"]
    try:
        proc = subprocess.Popen(cmd, cwd=PSX_DIR, close_fds=True, **get_no_window_kwargs())
        log(f"importre.py iniciado PID={proc.pid}")
        return proc.pid
    except Exception as e:
        log(f"Erro ao iniciar: {e}")
        return None


def main():
    log(f"=== Watchdog iniciado (psutil={HAS_PSUTIL}) ===")
    while True:
        try:
            # Monitorar importre.py
            pids = find_importre_pids()
            if not pids:
                log("importre.py morto — reiniciando")
                start_importre()
            elif len(pids) > 1:
                log(f"{len(pids)} processos duplicados: {pids}")
                # Manter o mais novo (último), matar os outros
                for pid in pids[:-1]:
                    log(f"Matando duplicado PID={pid}")
                    kill_pid(pid)
            else:
                # Verificar se log esta ativo (detectar travamento)
                stale = False
                try:
                    if os.path.exists(LOG_PATH):
                        mtime = os.path.getmtime(LOG_PATH)
                        age = time.time() - mtime
                        if age > STALE_LOG_THRESHOLD:
                            log(f"LOG STALE ({age/60:.0f}min) — PID={pids[0]} travado, reiniciando")
                            kill_pid(pids[0])
                            stale = True
                except Exception:
                    pass
                if not stale:
                    log(f"importre OK: PID={pids[0]}")

            # Monitorar servidor HTTP (dashboard) — max 1 instancia
            server_pids = find_server_pids()
            if len(server_pids) > 1:
                log(f"{len(server_pids)} servidores duplicados: matando TODOS e recriando 1")
                for pid in server_pids:
                    kill_pid(pid)
                time.sleep(1)
                start_server()
            elif not server_pids:
                log("Servidor HTTP morto — reiniciando")
                start_server()
            else:
                log(f"servidor OK: PID={server_pids[0]}")
        except Exception as e:
            log(f"Erro: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            log("Interrompido")
            break
        except Exception as e:
            log(f"FATAL: {e}")
            time.sleep(10)
