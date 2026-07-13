#!/usr/bin/env python3
"""Supervisor do _download_watchdog.py — reinicia se morrer."""

import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(r"D:\roms\library\roms\psx\_download_watchdog.py")


def get_pids():
    pids = []
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        out = subprocess.check_output(
            ["powershell", "-Command", "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*_download_watchdog.py*' -and $_.Name -eq 'python.exe' } | Select-Object ProcessId"],
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            startupinfo=si,
        )
        for line in out.decode("utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.isdigit():
                pids.append(int(line))
    except Exception:
        pass
    return pids


def start():
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
        )
    # Usar pythonw.exe se disponivel para nao ter console visivel
    python_exe = sys.executable
    if python_exe.lower().endswith("python.exe"):
        pythonw = python_exe[:-10] + "pythonw.exe"
        if Path(pythonw).exists():
            python_exe = pythonw
    return subprocess.Popen([python_exe, str(SCRIPT)], **kwargs)


def main():
    while True:
        pids = get_pids()
        if not pids:
            proc = start()
            print(f"Download watchdog iniciado: PID {proc.pid}")
        time.sleep(30)


if __name__ == "__main__":
    main()
