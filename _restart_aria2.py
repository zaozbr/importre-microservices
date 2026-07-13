"""Para e reinicia o daemon aria2c com nova config."""
import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _aria2_manager import Aria2Manager

m = Aria2Manager()
print(f"Daemon rodando: {m.is_daemon_running()}")

# Parar daemon
m.stop_daemon()
print("Daemon parado")

# Reiniciar
import time
time.sleep(2)
ok = m.start_daemon()
print(f"Daemon reiniciado: {ok}")

# Verificar config
if ok:
    opts = m._call("aria2.getGlobalOption", [])
    print(f"max-concurrent-downloads: {opts.get('max-concurrent-downloads')}")
    print(f"max-connection-per-server: {opts.get('max-connection-per-server')}")
    print(f"split: {opts.get('split')}")
