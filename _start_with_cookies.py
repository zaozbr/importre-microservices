"""Inicia aria2c limpo com cookies e popula com URLs."""
import json
import os
import re
import time
import requests
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote

STATE = r"D:\roms\library\roms\_importre_state"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
DOWNLOAD_DIR = os.path.join(STATE, "downloads")

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _aria2_manager

# 1. Iniciar aria2c
print("1. Iniciando aria2c com cookies...")
mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
mgr.start_daemon()
time.sleep(3)
print(f"   running: {mgr.is_daemon_running()}")

# 2. Verificar log — erros de cookies?
log_path = os.path.join(STATE, "aria2c.log")
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if content:
        print(f"   Log: {len(content)} chars")
        # Mostrar primeiras linhas
        for line in content.split("\n")[:10]:
            if line.strip():
                print(f"   {line[:120]}")
    else:
        print("   Log vazio (bom — sem erros)")

# 3. Gerar URLs frescas coolrom
print("\n2. Gerando URLs frescas CoolROM...")
coolrom_cache = json.load(open(os.path.join(STATE, "coolrom_cache.json"), "r", encoding="utf-8"))

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

def normalize_name(name):
    name = name.lower()
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()

def extract_words(name):
    stop = {'the', 'and', 'for', 'with', 'from', 'vol', 'volume', 'disc', 'japan', 'europe', 'usa'}
    return [w for w in re.findall(r'[a-z0-9]{3,}', name.lower()) if w not in stop]

cache_normalized = {}
for cache_name, cache_info in coolrom_cache.items():
    norm = normalize_name(cache_name)
    words = set(extract_words(norm))
    if words:
        cache_normalized[cache_name] = {"norm": norm, "words": words, "info": cache_info}

matches = []
for serial, name in all_pending.items():
    jp_norm = normalize_name(name)
    jp_words = set(extract_words(jp_norm))
    if not jp_words:
        continue
    best_match = None
    best_score = 0
    for cache_name, cache_data in cache_normalized.items():
        intersection = jp_words & cache_data["words"]
        if not intersection:
            continue
        score = len(intersection) / max(len(jp_words), len(cache_data["words"]))
        if score > best_score:
            best_score = score
            best_match = (cache_name, cache_data["info"])
    if best_match and best_score >= 0.5:
        matches.append((serial, name, best_match[1], best_score))

print(f"   Matches: {len(matches)}")

def fetch_fresh_dl_url(detail_info):
    if isinstance(detail_info, dict):
        href = detail_info.get("url", "")
    else:
        href = detail_info
    if not href:
        return None
    url = f"https://coolrom.com{href}" if href.startswith("/") else href
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        if resp.status_code != 200:
            return None
        dl_pattern = re.compile(r'(https?://dl\.coolrom\.com/[^"\'\s<>]+)')
        m = dl_pattern.search(resp.text)
        if m:
            return m.group(1)
        js_pattern = re.compile(r'dl\.coolrom\.com/([^"\'\s<>;]+)')
        m = js_pattern.search(resp.text)
        if m:
            return f"https://dl.coolrom.com/{m.group(1)}"
        return None
    except:
        return None

coolrom_urls = {}
with ThreadPoolExecutor(max_workers=20) as executor:
    futures = {executor.submit(fetch_fresh_dl_url, info): serial
               for serial, name, info, score in matches}
    for future in as_completed(futures):
        serial = futures[future]
        url = future.result()
        if url:
            coolrom_urls[serial] = url

print(f"   URLs coolrom: {len(coolrom_urls)}")

# 4. URLs archive (TODAS coleções, com cookies)
print("\n3. URLs archive.org (com auth)...")
archive_index = {}
for name in ["archive_name_index.json", "archive_jp_index.json"]:
    p = os.path.join(STATE, name)
    if os.path.exists(p):
        d = json.load(open(p, "r", encoding="utf-8"))
        archive_index.update(d)

archive_urls = {}
for serial, name in all_pending.items():
    if serial in coolrom_urls:
        continue
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
                archive_urls[serial] = url

print(f"   URLs archive: {len(archive_urls)}")

# 5. Popular aria2c
print("\n4. Populando aria2c...")
added = 0
for serial, url in coolrom_urls.items():
    try:
        filename = unquote(url.split("/")[-1])
        mgr.add_uri(url, dest_dir=DOWNLOAD_DIR, filename=f"{serial}_{filename}")
        added += 1
    except:
        pass
print(f"   CoolROM: {added}")

added2 = 0
for serial, url in archive_urls.items():
    try:
        filename = unquote(url.split("/")[-1])
        mgr.add_uri(url, dest_dir=DOWNLOAD_DIR, filename=f"{serial}_{filename}")
        added2 += 1
    except:
        pass
print(f"   Archive: {added2}")

# 6. Monitorar
print(f"\n5. Monitorando ({added + added2} URLs)...")
for i in range(12):
    time.sleep(10)
    try:
        stat = mgr.get_global_stat()
        speed = int(stat.get("downloadSpeed", 0))
        speed_mb = speed / 1024 / 1024
        active = stat.get("numActive")
        stopped = stat.get("numStopped")
        
        # Verificar log para erros
        errors = ""
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                log_content = f.read()
            error_count = log_content.count("[ERROR]")
            if error_count > 0:
                errors = f" errors={error_count}"
        
        marker = "OK" if speed_mb >= 20 else ("WARN" if speed_mb >= 5 else "LOW")
        print(f"   [{(i+1)*10:3d}s] {marker} {speed_mb:6.2f}MB/s active={active} stopped={stopped}{errors}")
    except Exception as e:
        print(f"   [{(i+1)*10}s] erro: {e}")

# Mostrar log final
print("\n6. Log do aria2c (últimas 20 linhas):")
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for line in lines[-20:]:
        if line.strip():
            print(f"   {line.rstrip()[:120]}")
