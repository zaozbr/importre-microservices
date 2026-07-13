"""Inicia todos os componentes em background via subprocess.Popen (detached)."""
import subprocess, os, time, sys

PSX = r"D:\roms\library\roms\psx"
ENV = os.environ.copy()
ENV["PATH"] = r"C:\aria2;" + ENV.get("PATH", "")
ENV["PYTHONIOENCODING"] = "utf-8"

# 1. Supervisor importre
print("1. Iniciando importre_supervisor.py...")
p1 = subprocess.Popen(
    ["py", "importre_supervisor.py"],
    cwd=PSX, env=ENV,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    stdin=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
)
print(f"   PID={p1.pid}")

# 2. Supervisor CHD
print("2. Iniciando _chd_supervisor.py...")
p2 = subprocess.Popen(
    ["py", "_chd_supervisor.py"],
    cwd=PSX, env=ENV,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    stdin=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
)
print(f"   PID={p2.pid}")

# 3. Monitor
print("3. Iniciando _monitor_importre.py...")
p3 = subprocess.Popen(
    ["py", "_monitor_importre.py"],
    cwd=PSX, env=ENV,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    stdin=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
)
print(f"   PID={p3.pid}")

# Aguardar 15s
print("\nAguardando 15s para subprocessos iniciarem...")
time.sleep(15)

# Verificar
import subprocess as sp
r = sp.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"], capture_output=True, text=True)
py_count = r.stdout.count("python.exe")
r2 = sp.run(["tasklist", "/FI", "IMAGENAME eq pythonw.exe", "/FO", "CSV"], capture_output=True, text=True)
pyw_count = r2.stdout.count("pythonw.exe")
r3 = sp.run(["tasklist", "/FI", "IMAGENAME eq aria2c.exe", "/FO", "CSV"], capture_output=True, text=True)
aria2_count = r3.stdout.count("aria2c.exe")

print(f"\npython.exe: {py_count}")
print(f"pythonw.exe: {pyw_count}")
print(f"aria2c.exe: {aria2_count}")

# Verificar portas
r4 = sp.run(["netstat", "-ano"], capture_output=True, text=True)
has_8765 = ":8765" in r4.stdout
has_6801 = ":6801" in r4.stdout
print(f"Porta 8765 (dashboard): {'SIM' if has_8765 else 'NAO'}")
print(f"Porta 6801 (aria2c RPC): {'SIM' if has_6801 else 'NAO'}")
