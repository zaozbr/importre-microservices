"""Remove downloads coolrom com 403 do aria2c e adiciona apenas archive.org.
CoolROM URLs expiram em 1h — não vale mais a pena usar.
Archive.org com cookies funciona a 60MB/s.
"""
import json
import os
import time
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _aria2_manager

STATE = r"D:\roms\library\roms\_importre_state"
DOWNLOAD_DIR = os.path.join(STATE, "downloads")

mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
if not mgr.is_daemon_running():
    print("Iniciando aria2c...")
    mgr.start_daemon()
    time.sleep(3)

# 1. Remover downloads coolrom (403)
print("1. Removendo downloads coolrom (403)...")
active = mgr.tell_active()
removed = 0
archive_active = 0
for d in active:
    files = d.get("files", [])
    url = files[0]["uris"][0]["uri"] if files and files[0].get("uris") else ""
    if "coolrom" in url:
        try:
            mgr.remove(d.get("gid"))
            removed += 1
        except:
            pass
    elif "archive" in url:
        archive_active += 1
print(f"   Removidos: {removed} coolrom, Mantidos: {archive_active} archive")

# 2. Adicionar mais URLs archive.org
print("\n2. Adicionando URLs archive.org restantes...")
q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
queue = q.get("queue", [])
completed = set(q.get("completed", {}).keys()) if isinstance(q.get("completed"), dict) else set()
failed = set(q.get("failed", {}).keys()) if isinstance(q.get("failed"), dict) else set()
ip = set(q.get("in_progress", {}).keys()) if isinstance(q.get("in_progress"), dict) else set()

all_pending = {}
for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else str(item)
    name = item.get("name", "") if isinstance(item, dict) else ""
    if serial in completed or serial in failed or serial in ip:
        continue
    all_pending[serial] = name

print(f"   Pending: {len(all_pending)}")

# Carregar índice archive
archive_index = {}
for name in ["archive_name_index.json", "archive_jp_index.json"]:
    p = os.path.join(STATE, name)
    if os.path.exists(p):
        d = json.load(open(p, "r", encoding="utf-8"))
        archive_index.update(d)

# URLs já no aria2c
active = mgr.tell_active()
waiting = mgr.tell_waiting(0, 500)
existing_urls = set()
for d in active + waiting:
    files = d.get("files", [])
    if files and files[0].get("uris"):
        existing_urls.add(files[0]["uris"][0]["uri"])

archive_urls = {}
for serial, name in all_pending.items():
    if serial in archive_index:
        info = archive_index[serial]
        if isinstance(info, dict):
            url = info.get("download_url")
            if not url and info.get("collection") and info.get("file"):
                fname = info["file"].replace(" ", "%20").replace("(", "%28").replace(")", "%29")
                url = f"https://archive.org/download/{info['collection']}/{fname}"
            if url and url not in existing_urls:
                archive_urls[serial] = url

print(f"   Novas URLs archive: {len(archive_urls)}")

added = 0
for serial, url in archive_urls.items():
    try:
        filename = unquote(url.split("/")[-1])
        mgr.add_uri(url, dest_dir=DOWNLOAD_DIR, filename=f"{serial}_{filename}")
        added += 1
    except:
        pass
print(f"   Adicionadas: {added}")

# 3. Monitorar
print(f"\n3. Monitorando (120s)...")
log_path = os.path.join(STATE, "aria2c.log")
for i in range(12):
    time.sleep(10)
    try:
        stat = mgr.get_global_stat()
        speed = int(stat.get("downloadSpeed", 0))
        speed_mb = speed / 1024 / 1024
        active = stat.get("numActive")
        stopped = stat.get("numStopped")
        
        errors = 0
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    errors = f.read().count("[ERROR]")
            except:
                pass
        
        completed = 0
        if int(stopped) > 0:
            try:
                stopped_list = mgr.tell_stopped(0, 200)
                completed = sum(1 for d in stopped_list if d.get("status") == "complete")
            except:
                pass
        
        marker = "OK" if speed_mb >= 20 else ("WARN" if speed_mb >= 5 else "LOW")
        print(f"   [{(i+1)*10:3d}s] {marker} {speed_mb:6.2f}MB/s active={active} stopped={stopped} completed={completed} errors={errors}")
    except Exception as e:
        print(f"   [{(i+1)*10}s] erro: {str(e)[:60]}")
