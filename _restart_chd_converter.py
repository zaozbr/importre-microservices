"""Reinicia o conversor CHD forcando um rescan completo."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PSX_DIR = Path(r"D:\roms\library\roms\psx")
STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
PROGRESS_PATH = PSX_DIR / "_chd_convert_progress.json"
LOCK_PATH = PSX_DIR / "_chd_convert.lock"
CHDMAN = str(PSX_DIR / "chdman.exe")


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


# Encontrar e matar processo do conversor CHD (porta 8766)
def get_chd_converter_pid():
    try:
        # Listar conexoes na porta 8766
        proc = subprocess.run(
            ["powershell", "-Command",
             "Get-NetTCPConnection -LocalPort 8766 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"],
            capture_output=True, text=True, timeout=10
        )
        pids = [int(x) for x in proc.stdout.strip().splitlines() if x.strip().isdigit()]
        return pids[0] if pids else None
    except Exception:
        return None


pid = get_chd_converter_pid()
if pid:
    print(f"Matando conversor CHD PID {pid}")
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True)
    time.sleep(2)
else:
    print("Conversor CHD nao encontrado na porta 8766")

# Remover progresso e lock para forcar rescan
for p in [PROGRESS_PATH, LOCK_PATH]:
    if p.exists():
        p.unlink()
        print(f"Removido: {p}")

# Iniciar conversor em background
print("Iniciando conversor CHD...")
subprocess.Popen(
    ["python", str(PSX_DIR / "_chd_convert_v2.py"), "--workers", "4"],
    **get_no_window_kwargs(),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print("Conversor CHD reiniciado. Dashboard: http://127.0.0.1:8766")
