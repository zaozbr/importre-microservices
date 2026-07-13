"""Supervisor autonomo para _site_discovery.py.
Reinicia o descobridor se morrer ou travar.
"""
import subprocess
import time
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "_site_discovery.py"
PYTHON = sys.executable


def get_no_window_kwargs():
    kwargs = {}
    if sys.platform == "win32":
        import subprocess as sp
        si = sp.STARTUPINFO()
        si.dwFlags |= sp.STARTF_USESHOWWINDOW
        si.wShowWindow = sp.SW_HIDE
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = (
            sp.CREATE_NO_WINDOW
            | sp.DETACHED_PROCESS
            | sp.CREATE_NEW_PROCESS_GROUP
            | sp.CREATE_BREAKAWAY_FROM_JOB
        )
    return kwargs


def is_discovery_running():
    try:
        import psutil
        for p in psutil.process_iter(["pid", "cmdline"]):
            cmd = " ".join(p.info["cmdline"] or [])
            if "_site_discovery.py" in cmd and "supervisor" not in cmd:
                return True
        return False
    except Exception:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10
        )
        return "_site_discovery.py" in result.stdout


def start_discovery():
    # Usar pythonw.exe se disponivel para evitar console visivel
    python_exe = PYTHON
    if python_exe.lower().endswith("python.exe"):
        pythonw = python_exe[:-10] + "pythonw.exe"
        if Path(pythonw).exists():
            python_exe = pythonw
    cmd = [python_exe, str(SCRIPT)]
    subprocess.Popen(cmd, **get_no_window_kwargs())
    print(f"[supervisor] _site_discovery.py iniciado")


def main():
    print("[supervisor] Site Discovery Supervisor iniciado")
    while True:
        try:
            if not is_discovery_running():
                print("[supervisor] _site_discovery.py nao encontrado — reiniciando...")
                start_discovery()
            else:
                print("[supervisor] _site_discovery.py OK")
        except Exception as e:
            print(f"[supervisor] erro: {e}")
        time.sleep(60)


if __name__ == "__main__":
    main()
