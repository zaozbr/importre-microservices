"""FAST BOOT: mata tudo, inicia aria2c com cookies, popula archive.org, monitora."""
import json, os, time, sys, subprocess
from urllib.parse import unquote

STATE = r"D:\roms\library\roms\_importre_state"
DLDIR = os.path.join(STATE, "downloads")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _aria2_manager

# 1. Garantir que aria2c está morto
subprocess.run(["taskkill", "/F", "/IM", "aria2c.exe"], capture_output=True)
time.sleep(2)

# 2. Limpar session
open(os.path.join(STATE, "aria2_session.txt"), "w").close()
open(os.path.join(STATE, "aria2c.log"), "w").close()

# 3. Iniciar aria2c
mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
mgr.start_daemon()
time.sleep(3)
running = mgr.is_daemon_running()
print(f"aria2c running: {running}")
if not running:
    print("FALHOU!")
    sys.exit(1)

# 4. Carregar fila
q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
queue = q.get("queue", [])
completed = set(q.get("completed", {}).keys()) if isinstance(q.get("completed"), dict) else set()
failed = set(q.get("failed", {}).keys()) if isinstance(q.get("failed"), dict) else set()
ip = set(q.get("in_progress", {}).keys()) if isinstance(q.get("in_progress"), dict) else set()

pending = {}
for item in queue:
    s = item.get("serial", "") if isinstance(item, dict) else str(item)
    n = item.get("name", "") if isinstance(item, dict) else ""
    if s not in completed and s not in failed and s not in ip:
        pending[s] = n
print(f"Pending: {len(pending)}")

# 5. Carregar índice archive
archive_index = {}
for name in ["archive_name_index.json", "archive_jp_index.json"]:
    p = os.path.join(STATE, name)
    if os.path.exists(p):
        archive_index.update(json.load(open(p, "r", encoding="utf-8")))

# 6. Construir URLs archive (HTTPS + cookies)
urls = {}
for serial, name in pending.items():
    if serial in archive_index:
        info = archive_index[serial]
        if isinstance(info, dict):
            url = info.get("download_url")
            if not url and info.get("collection") and info.get("file"):
                fname = info["file"].replace(" ", "%20").replace("(", "%28").replace(")", "%29")
                url = f"https://archive.org/download/{info['collection']}/{fname}"
            if url:
                if url.startswith("http://"):
                    url = "https://" + url[7:]
                urls[serial] = url

print(f"URLs archive: {len(urls)}")

# 7. Popular aria2c
added = 0
for serial, url in urls.items():
    try:
        fn = unquote(url.split("/")[-1])
        mgr.add_uri(url, dest_dir=DLDIR, filename=f"{serial}_{fn}")
        added += 1
    except:
        pass
print(f"Adicionadas: {added}")

# 8. Monitorar 60s
print("\nMonitorando...")
for i in range(6):
    time.sleep(10)
    try:
        stat = mgr.get_global_stat()
        speed = int(stat.get("downloadSpeed", 0))
        mb = speed / 1024 / 1024
        a = stat.get("numActive")
        s = stat.get("numStopped")
        m = "OK" if mb >= 20 else ("WARN" if mb >= 5 else "LOW")
        print(f"  [{(i+1)*10:3d}s] {m} {mb:.2f}MB/s active={a} stopped={s}")
    except:
        print(f"  [{(i+1)*10}s] RPC timeout (aria2c ocupado)")
