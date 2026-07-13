"""Reinicia o importre se nao estiver rodando."""
import subprocess
import sys
import time
from pathlib import Path

psx = Path(r"D:\roms\library\roms\psx")


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


# Verificar se importre esta rodando
def is_importre_running():
    try:
        proc = subprocess.run(
            ["powershell", "-Command",
             "Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"],
            capture_output=True, text=True, timeout=5
        )
        pids = [int(x) for x in proc.stdout.strip().splitlines() if x.strip().isdigit()]
        return pids[0] if pids else None
    except Exception:
        return None


pid = is_importre_running()
if pid:
    print(f"Importre ja rodando PID {pid}")
else:
    print("Importre nao esta rodando. Iniciando...")
    subprocess.Popen(
        ["python", str(psx / "start_system.py")],
        **get_no_window_kwargs(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    pid = is_importre_running()
    print(f"Importre PID apos iniciar: {pid}")
