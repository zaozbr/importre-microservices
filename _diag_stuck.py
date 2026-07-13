"""Diagnostica downloads stuck no aria2c — verifica errorCode."""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _aria2_manager

mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
active = mgr.tell_active()

# Categorizar
stuck = []
downloading = []
for d in active:
    comp = int(d.get("completedLength", 0))
    total = int(d.get("totalLength", 0))
    speed = int(d.get("downloadSpeed", 0))
    status = d.get("status", "")
    err = d.get("errorCode", "0")
    files = d.get("files", [])
    url = files[0]["uris"][0]["uri"] if files and files[0].get("uris") else "?"
    
    if comp == 0 and speed == 0:
        stuck.append((d.get("gid"), url, err, status))
    else:
        downloading.append((d.get("gid"), comp, total, speed, url))

print(f"=== DOWNLOADS ATIVOS ({len(active)}) ===")
print(f"  Baixando: {len(downloading)}")
print(f"  Stuck (0/0): {len(stuck)}")

print(f"\n=== STUCK — análise de erros ===")
error_codes = {}
for gid, url, err, status in stuck:
    error_codes[err] = error_codes.get(err, 0) + 1

for err, count in sorted(error_codes.items(), key=lambda x: -x[1]):
    print(f"  errorCode={err}: {count} downloads")

# Mostrar URLs dos stuck
print(f"\n=== URLs STUCK (primeiros 20) ===")
for gid, url, err, status in stuck[:20]:
    # Identificar fonte
    if "coolrom" in url:
        fonte = "coolrom"
    elif "archive.org" in url:
        fonte = "archive"
    else:
        fonte = "other"
    print(f"  [{fonte}] err={err} {url[:90]}")

# Verificar stopped (completados/falhas)
stopped = mgr.tell_stopped(0, 20)
print(f"\n=== STOPPED ({len(stopped)}) ===")
for d in stopped:
    status = d.get("status")
    comp = int(d.get("completedLength", 0))
    total = int(d.get("totalLength", 0))
    err = d.get("errorCode", "0")
    files = d.get("files", [])
    url = files[0]["uris"][0]["uri"] if files and files[0].get("uris") else "?"
    size_mb = total / 1024 / 1024
    print(f"  {status}: {size_mb:.0f}MB err={err} {url[:80]}")

# Estatísticas globais
stat = mgr.get_global_stat()
speed = int(stat.get("downloadSpeed", 0))
print(f"\n=== GLOBAL ===")
print(f"  active={stat.get('numActive')} waiting={stat.get('numWaiting')} stopped={stat.get('numStopped')}")
print(f"  speed: {speed/1024/1024:.2f}MB/s ({speed/1024:.0f}KB/s)")
