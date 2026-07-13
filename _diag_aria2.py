"""Diagnóstico detalhado do aria2c."""
import sys, json
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _aria2_manager import Aria2Manager

m = Aria2Manager()
stat = m.get_global_stat()
print(f"Active: {stat.get('active', 0)}")
print(f"Waiting: {stat.get('waiting', 0)}")
print(f"Stopped: {stat.get('stopped', 0)}")
print(f"Speed: {int(stat.get('downloadSpeed', 0)) / 1e6:.2f} MB/s")

active = m.tell_active()
print(f"\n=== {len(active)} DOWNLOADS ATIVOS ===")
for d in active:
    total = int(d.get("totalLength", 0))
    completed = int(d.get("completedLength", 0))
    speed = int(d.get("downloadSpeed", 0))
    conns = int(d.get("connections", 0))
    files = d.get("files", [{}])
    path = files[0].get("path", "") if files else ""
    url = ""
    if files and files[0].get("uris"):
        url = files[0]["uris"][0].get("uri", "")
    pct = (completed / total * 100) if total > 0 else 0
    fname = path.split("\\")[-1] if path else "?"
    print(f"  {fname[:40]:40s} {completed/1e6:7.1f}/{total/1e6:7.1f}MB {pct:5.1f}% {speed/1e6:5.2f}MB/s c={conns} {url[:60]}")

waiting = m.tell_waiting(0, 50)
print(f"\n=== {len(waiting)} DOWNLOADS NA FILA ===")
for d in waiting[:10]:
    files = d.get("files", [{}])
    path = files[0].get("path", "") if files else ""
    fname = path.split("\\")[-1] if path else "?"
    print(f"  {fname[:50]}")
