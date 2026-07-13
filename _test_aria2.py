"""Teste rápido: baixar 1 arquivo via aria2c com multi-chunk."""
import sys, os, time
sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
from _aria2_manager import Aria2Manager

m = Aria2Manager()
if not m.is_daemon_running():
    print("Iniciando daemon...")
    m.start_daemon()

# URL de teste: archive.org CHD JP (URL real que o importre usa)
url = "https://archive.org/download/psx-ntscj-chd-zstd/ntscj/NOeL%203%20-%20Mission%20on%20the%20Line%20%28Japan%29%20%28Disc%201%29%20%28Major%20Wave%29.chd"
dest = r"D:\roms\library\roms\_importre_state\downloads"

print(f"Adicionando: {url}")
gid = m.add_uri(url, dest_dir=dest)
print(f"GID: {gid}")

# Monitorar progresso por 60s
for i in range(20):
    info = m.get_download_info(gid)
    state = info["status"]
    completed_mb = info["completed_length"] / 1e6
    total_mb = info["total_length"] / 1e6
    speed_mbs = info["download_speed"] / 1e6
    pct = info["progress_pct"]
    conns = info["connections"]
    print(f"  [{i*3:3d}s] {state:10s} {completed_mb:8.1f}/{total_mb:8.1f}MB ({pct:5.1f}%) {speed_mbs:6.1f}MB/s conns={conns}")
    if state in ("complete", "error", "removed"):
        break
    time.sleep(3)

print(f"\nStatus final: {info['status']}")
if info["status"] == "complete":
    print(f"Arquivo: {info['filename']}")
    print(f"Tamanho: {info['completed_length']/1e6:.1f}MB")
    print("SUCESSO!")
else:
    print(f"Erro: {info.get('error_message', '')}")
