import subprocess
import re
import sys


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
    print("no servers")
    exit(0)

pids = []
for line in result.stdout.splitlines():
    if "importre_server.py" not in line:
        continue
    m = re.search(r"(\d+)\s*$", line)
    if m:
        pids.append(int(m.group(1)))

if len(pids) <= 1:
    print(f"found {len(pids)} server(s), nothing to kill")
    exit(0)

print(f"found {len(pids)} importre_server.py processes: {pids}")
for pid in pids[1:]:
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], **get_run_kwargs(10))
        print(f"killed {pid}")
    except Exception as e:
        print(f"error killing {pid}: {e}")
print(f"kept {pids[0]}")
