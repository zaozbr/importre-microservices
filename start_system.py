"""Inicia os supervisores do importre e do conversor CHD em background.
Use este script para iniciar o sistema completo apos reboot."""
import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
IMPORTRE_SUP = SCRIPT_DIR / "importre_supervisor.py"
CHD_SUP = SCRIPT_DIR / "_chd_supervisor.py"


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


def get_run_kwargs(timeout=None):
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


def is_running(pattern):
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             f"Get-WmiObject Win32_Process -Filter \"Name='python.exe'\" | "
             f"Where-Object {{ $_.CommandLine -like '*{pattern}*' }} | "
             "Select-Object ProcessId | ConvertTo-Json"],
            **get_run_kwargs(10)
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, list):
                return [int(d["ProcessId"]) for d in data]
            return [int(data["ProcessId"])]
    except Exception:
        pass
    return []


def start_supervisor(script_path, name):
    if is_running(script_path.name):
        print(f"Supervisor {name} ja esta rodando — nada a fazer")
        return None
    print(f"Iniciando supervisor {name}...")
    proc = subprocess.Popen(
        ["python", str(script_path)],
        **get_no_window_kwargs(),
    )
    print(f"Supervisor {name} iniciado (PID {proc.pid})")
    return proc


def safe_print(msg):
    try:
        print(msg)
    except OSError:
        pass


safe_print("Iniciando sistema completo de ROMs PSX...")
start_supervisor(IMPORTRE_SUP, "importre")
start_supervisor(CHD_SUP, "chd")

safe_print("\nMonitores:")
safe_print("  importre: D:\\roms\\library\\roms\\_importre_state\\supervisor.log")
safe_print("  CHD:      D:\\roms\\library\\roms\\psx\\_chd_supervisor.log")
safe_print("Dashboards:")
safe_print("  importre: http://127.0.0.1:8765")
safe_print("  CHD:      http://127.0.0.1:8766")
