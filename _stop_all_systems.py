"""Para todos os sistemas: conversor CHD, importre, supervisor."""
import subprocess
import time
from pathlib import Path

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

print("Parando importre (porta 8765)...")
for pid in get_pids_on_port(8765):
    kill_pid(pid)

print("Buscando processos python relacionados...")
proc = subprocess.run(
    ["powershell", "-Command",
     "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Select-Object ProcessId, CommandLine | Format-Table -AutoSize"],
    capture_output=True, text=True, timeout=10
)
lines = proc.stdout.splitlines()
for line in lines:
    if any(x in line for x in ["importre", "chd_convert", "start_system", "supervisor"]):
        # extrair pid
        import re
        m = re.match(r"\s*(\d+)", line)
        if m:
            pid = int(m.group(1))
            kill_pid(pid)

time.sleep(2)
print("\nVerificando portas:")
for port in [8765, 8766]:
    pids = get_pids_on_port(port)
    print(f"  Porta {port}: {pids if pids else 'livre'}")

print("\nSistema parado.")
