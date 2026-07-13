import subprocess
import re
import sys
import time


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
            | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
        )
    return kwargs


result = subprocess.run(
    ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine"],
    **get_run_kwargs(15)
)
if result.returncode != 0 or not result.stdout.strip():
    print("no python processes")
    exit(0)

own_pid = str(sys.modules["os"].getpid())
pids = []
for line in result.stdout.splitlines():
    if r"roms\psx" not in line and r"roms\\psx" not in line:
        continue
    m = re.search(r"(\d+)\s*$", line)
    if not m:
        continue
    pid = m.group(1)
    if pid == own_pid:
        continue
    pids.append(pid)

print(f"found {len(pids)} psx python processes")
for pid in pids:
    try:
        subprocess.run(["taskkill", "/PID", pid, "/F"], **get_run_kwargs(10))
        print(f"killed {pid}")
    except Exception as e:
        print(f"error killing {pid}: {e}")
print("done")
