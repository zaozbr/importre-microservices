# Parar apenas o conversor CHD (porta 8766). Nao afeta o importre.
import subprocess
import time
import re

def get_pids_on_port(port):
    try:
        proc = subprocess.run(
            ["powershell", "-Command",
            f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"],
            capture_output=True, text=True, timeout=5
        )
        return [int(x) for x in proc.stdout.strip().splitlines() if x.strip().isdigit()]
    except Exception:
        return []

def kill_pid(pid):
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True, timeout=5)
        print(f"Matou PID {pid}")
    except Exception as e:
        print(f"Erro ao matar PID {pid}: {e}")

print("Parando conversor CHD (porta 8766)...")
for pid in get_pids_on_port(8766):
    kill_pid(pid)

print("Buscando processos python do CHD...")
proc = subprocess.run(
    ["powershell", "-Command",
     "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Select-Object ProcessId, CommandLine | Format-Table -AutoSize"],
    capture_output=True, text=True, timeout=10
)
for line in proc.stdout.splitlines():
    if any(x in line for x in ["_chd_convert_v2.py", "_chd_supervisor.py"]):
        m = re.match(r"\s*(\d+)", line)
        if m:
            kill_pid(int(m.group(1)))

time.sleep(2)
pids = get_pids_on_port(8766)
print(f"\\nPorta 8766: {pids if pids else 'livre'}")
print("\\nConversor CHD parado.")
