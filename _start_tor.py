"""Inicia tor.exe como processo em background com SOCKS5 na porta 9050."""
import subprocess, time, os, sys

TOR_EXE = r"C:\Users\Usuario\Desktop\Tor Browser\Browser\TorBrowser\Tor\tor.exe"
TOR_DATA = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'tor_data')
TOR_LOG = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'tor.log')

os.makedirs(TOR_DATA, exist_ok=True)

# Escrever torrc minimo
torrc_path = os.path.join(TOR_DATA, 'torrc')
with open(torrc_path, 'w') as f:
    f.write(f"""
SocksPort 9050
DataDirectory {TOR_DATA}
Log notice file {TOR_LOG}
AvoidDiskWrites 1
""".strip())

print(f"torrc: {torrc_path}")
print(f"Iniciando tor.exe...")

# Iniciar tor.exe em background
proc = subprocess.Popen(
    [TOR_EXE, '-f', torrc_path],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    creationflags=subprocess.CREATE_NO_WINDOW
)

print(f"PID: {proc.pid}")

# Aguardar bootstrap
for i in range(30):
    time.sleep(2)
    # Verificar se o processo ainda esta rodando
    if proc.poll() is not None:
        stdout = proc.stdout.read().decode('utf-8', errors='replace')
        stderr = proc.stderr.read().decode('utf-8', errors='replace')
        print(f"tor.exe SAIU (code={proc.returncode})")
        print(f"stdout: {stdout[:500]}")
        print(f"stderr: {stderr[:500]}")
        sys.exit(1)

    # Verificar log
    if os.path.exists(TOR_LOG):
        with open(TOR_LOG, 'r', errors='replace') as f:
            log = f.read()
        if 'Bootstrapped 100%' in log:
            print(f"Tor bootstrap completo em {i*2}s!")
            print(f"SOCKS5 proxy ativo em 127.0.0.1:9050")
            break
        # Mostrar progresso
        lines = log.strip().split('\n')
        if lines:
            last = lines[-1][:120]
            print(f"  [{i*2}s] {last}")
else:
    print("Timeout aguardando bootstrap do Tor")
    if os.path.exists(TOR_LOG):
        with open(TOR_LOG, 'r', errors='replace') as f:
            print(f.read()[-500:])

print(f"\nTor rodando. PID={proc.pid}")
print(f"Para parar: taskkill /PID {proc.pid} /F")
