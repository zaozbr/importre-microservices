"""Pré-popula aria2c com URLs válidas do archive.org.
Corrige o parsing dos diferentes formatos de índice.
"""
import json
import os
import sys
import time
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _aria2_manager

state_dir = r"D:\roms\library\roms\_importre_state"

# Construir índice unificado de serial -> download_url
url_index = {}

# 1. archive_name_index.json (tem download_url direta)
p = os.path.join(state_dir, "archive_name_index.json")
if os.path.exists(p):
    d = json.load(open(p, "r", encoding="utf-8"))
    for serial, info in d.items():
        if isinstance(info, dict) and info.get("download_url"):
            url_index[serial] = info["download_url"]
    print(f"archive_name_index: {len(d)} entradas, {len([1 for v in d.values() if isinstance(v,dict) and v.get('download_url')])} com URL")

# 2. archive_jp_public_index.json (estrutura aninhada)
p = os.path.join(state_dir, "archive_jp_public_index.json")
if os.path.exists(p):
    d = json.load(open(p, "r", encoding="utf-8"))
    serial_idx = d.get("serial_index", {})
    for serial, info in serial_idx.items():
        if isinstance(info, dict):
            url = info.get("download_url")
            if not url and info.get("identifier") and info.get("filename"):
                # Construir URL: http://archive.org/download/{identifier}/{filename}
                fname = info["filename"].replace(" ", "%20").replace("(", "%28").replace(")", "%29")
                url = f"http://archive.org/download/{info['identifier']}/{fname}"
            if url:
                url_index[serial] = url
    print(f"archive_jp_public_index: serial_index com {len(serial_idx)} entradas")

# 3. archive_jp_index.json (collection + file -> construir URL)
p = os.path.join(state_dir, "archive_jp_index.json")
if os.path.exists(p):
    d = json.load(open(p, "r", encoding="utf-8"))
    for serial, info in d.items():
        if isinstance(info, dict) and info.get("collection") and info.get("file"):
            if serial not in url_index:  # não sobrescrever URLs já válidas
                fname = info["file"].replace(" ", "%20").replace("(", "%28").replace(")", "%29")
                url = f"http://archive.org/download/{info['collection']}/{fname}"
                url_index[serial] = url
    print(f"archive_jp_index: {len(d)} entradas (URLs construídas)")

print(f"\nÍndice unificado: {len(url_index)} URLs válidas")

# Carregar queue
q = json.load(open(os.path.join(state_dir, "queue.json"), "r", encoding="utf-8"))
queue = q.get("queue", [])
completed = set(q.get("completed", {}).keys()) if isinstance(q.get("completed"), dict) else set()
failed = set(q.get("failed", {}).keys()) if isinstance(q.get("failed"), dict) else set()
ip = set(q.get("in_progress", {}).keys()) if isinstance(q.get("in_progress"), dict) else set()

print(f"Queue: pending={len(queue)} completed={len(completed)} failed={len(failed)} ip={len(ip)}")

# Encontrar URLs para pending
urls_to_add = []
for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else str(item)
    if serial in completed or serial in failed or serial in ip:
        continue
    if serial in url_index:
        urls_to_add.append((serial, url_index[serial]))

print(f"URLs para adicionar: {len(urls_to_add)} (de {len(queue)} pending)")

# Mostrar amostra
for s, u in urls_to_add[:5]:
    print(f"  {s}: {u[:100]}")

# Conectar ao aria2c
mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
if not mgr.is_daemon_running():
    print("\nIniciando aria2c...")
    mgr.start_daemon()

# Limpar downloads existentes
try:
    active = mgr.tell_active()
    for d in active:
        mgr.remove(d.get("gid"))
    print(f"Removidos {len(active)} downloads ativos anteriores")
except:
    pass

# Adicionar URLs (máximo 80)
added = 0
failed_add = 0
download_dir = r"D:\roms\library\roms\_importre_state\downloads"

for serial, url in urls_to_add[:80]:
    try:
        from urllib.parse import unquote
        filename = unquote(url.split("/")[-1])
        dest_filename = f"{serial}_{filename}"
        
        gid = mgr.add_uri(url, dest_dir=download_dir, filename=dest_filename)
        added += 1
        if added % 20 == 0:
            print(f"  Adicionados: {added}/{min(len(urls_to_add), 80)}")
            time.sleep(0.5)  # não sobrecarregar Tor
    except Exception as e:
        failed_add += 1
        if failed_add <= 3:
            print(f"  ERRO adicionando {serial}: {e}")

print(f"\nResultado: {added} URLs adicionadas, {failed_add} falhas")

# Verificar estatísticas
try:
    stat = mgr.get_global_stat()
    print(f"\naria2c: active={stat.get('numActive')} waiting={stat.get('numWaiting')} stopped={stat.get('numStopped')}")
    speed = int(stat.get('downloadSpeed', 0))
    print(f"  downloadSpeed: {speed/1024/1024:.2f}MB/s ({speed/1024:.0f}KB/s)")
except Exception as e:
    print(f"Erro stat: {e}")
