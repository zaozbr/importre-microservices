"""Pipeline completo:
1. Para aria2c
2. Limpa arquivos órfãos (sem .aria2 control file)
3. Reinicia aria2c com --allow-overwrite=true
4. Gera URLs frescas do coolrom (visita páginas de detalhe em paralelo)
5. Adiciona URLs do archive.org (apenas coleções que funcionam)
6. Monitora velocidade
"""
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

# ============================================================
# 1. PARAR ARIA2C
# ============================================================
print("=" * 60)
print("1. Parando aria2c...")
subprocess.run(["taskkill", "/F", "/IM", "aria2c.exe"], capture_output=True)
time.sleep(2)
print("   OK")

# ============================================================
# 2. LIMPAR ARQUIVOS ÓRFÃOS
# ============================================================
print("\n2. Limpando arquivos órfãos (sem .aria2 control file)...")
if os.path.exists(DOWNLOAD_DIR):
    removed = 0
    kept = 0
    for f in os.listdir(DOWNLOAD_DIR):
        if f.endswith(".aria2"):
            continue  # control file — manter
        filepath = os.path.join(DOWNLOAD_DIR, f)
        if not os.path.isfile(filepath):
            continue
        control_file = filepath + ".aria2"
        if not os.path.exists(control_file):
            # Arquivo órfão — remover (será re-baixado)
            try:
                sz = os.path.getsize(filepath)
                os.remove(filepath)
                removed += 1
            except:
                pass
        else:
            kept += 1
    print(f"   Removidos: {removed} órfãos, Mantidos: {kept} com .aria2")

# Limpar session file
session_file = os.path.join(STATE, "aria2_session.txt")
open(session_file, "w").close()
print("   Session file limpo")

# ============================================================
# 3. REINICIAR ARIA2C
# ============================================================
print("\n3. Reiniciando aria2c com --allow-overwrite=true...")
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _aria2_manager

mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
mgr.start_daemon()
time.sleep(3)
if mgr.is_daemon_running():
    print("   aria2c rodando!")
else:
    print("   ERRO: aria2c não iniciou!")
    sys.exit(1)

# ============================================================
# 4. GERAR URLS FRESCAS DO COOLROM
# ============================================================
print("\n4. Gerando URLs frescas do CoolROM...")

# Carregar cache coolrom (por nome)
coolrom_cache = json.load(open(os.path.join(STATE, "coolrom_cache.json"), "r", encoding="utf-8"))
jp_entries = {k: v for k, v in coolrom_cache.items() if "japan" in k.lower()}
print(f"   Cache JP: {len(jp_entries)} entradas")

# Carregar pending JP
q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
queue = q.get("queue", [])
completed = set(q.get("completed", {}).keys()) if isinstance(q.get("completed"), dict) else set()
failed = set(q.get("failed", {}).keys()) if isinstance(q.get("failed"), dict) else set()
ip = set(q.get("in_progress", {}).keys()) if isinstance(q.get("in_progress"), dict) else set()

jp_pending = {}
for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else str(item)
    name = item.get("name", "") if isinstance(item, dict) else ""
    if serial.startswith(("SLPM", "SLPS", "SLPH", "SCPS", "SIPS")):
        if serial not in completed and serial not in failed and serial not in ip:
            jp_pending[serial] = name

print(f"   JP pending: {len(jp_pending)}")

# Match fuzzy
def normalize_name(name):
    name = name.lower()
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()

def extract_words(name):
    stop = {'the', 'and', 'for', 'with', 'from', 'vol', 'volume', 'disc', 'japan', 'europe', 'usa'}
    return [w for w in re.findall(r'[a-z0-9]{3,}', name.lower()) if w not in stop]

cache_normalized = {}
for cache_name, cache_info in jp_entries.items():
    norm = normalize_name(cache_name)
    words = set(extract_words(norm))
    if words:
        cache_normalized[cache_name] = {"norm": norm, "words": words, "info": cache_info}

matches = []
for serial, jp_name in jp_pending.items():
    jp_norm = normalize_name(jp_name)
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
        matches.append((serial, jp_name, best_match[1], best_score))

print(f"   Matches: {len(matches)}")

# Buscar URLs frescas em paralelo
def fetch_fresh_dl_url(detail_info):
    """Visita página de detalhe do coolrom e extrai URL fresca dl.coolrom.com."""
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
        # Procurar por link dl.coolrom.com
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
    done = 0
    for future in as_completed(futures):
        serial = futures[future]
        done += 1
        url = future.result()
        if url:
            coolrom_urls[serial] = url
            if done <= 10 or done % 20 == 0:
                print(f"   ✓ [{done}/{len(matches)}] {serial}")
        elif done <= 3:
            print(f"   ✗ [{done}/{len(matches)}] {serial}: sem URL")

print(f"   URLs coolrom frescas: {len(coolrom_urls)}")

# ============================================================
# 5. ADICIONAR URLS ARCHIVE.ORG (coleções que funcionam)
# ============================================================
print("\n5. Adicionando URLs archive.org (coleções válidas)...")

# Coleções que funcionam (baseado no log: apenas psx-ntscj-chd-zstd e CuratedPSXRedumpCHDs)
# psx-ntscj-chd-zstd tem alguns 500 mas alguns funcionam
# CuratedPSXRedumpCHDs funcionou (2 completaram)
# Redump_PSX_2021_06_04_* retorna 403
# psx-pal-chd-zstd retorna auth failed
GOOD_COLLECTIONS = {"psx-ntscj-chd-zstd", "CuratedPSXRedumpCHDs", "psx-chd-roms-m"}

archive_index = {}
for name in ["archive_name_index.json", "archive_jp_index.json"]:
    p = os.path.join(STATE, name)
    if os.path.exists(p):
        d = json.load(open(p, "r", encoding="utf-8"))
        archive_index.update(d)

archive_urls = {}
for serial, jp_name in jp_pending.items():
    if serial in coolrom_urls:
        continue  # coolrom é prioritário (mais rápido)
    if serial in archive_index:
        info = archive_index[serial]
        if isinstance(info, dict):
            url = info.get("download_url")
            if not url and info.get("collection") and info.get("file"):
                collection = info["collection"]
                if collection in GOOD_COLLECTIONS:
                    fname = info["file"].replace(" ", "%20").replace("(", "%28").replace(")", "%29")
                    url = f"http://archive.org/download/{collection}/{fname}"
            if url:
                # Filtrar apenas coleções boas
                for coll in GOOD_COLLECTIONS:
                    if coll in url:
                        archive_urls[serial] = url
                        break

print(f"   URLs archive (coleções válidas): {len(archive_urls)}")

# ============================================================
# 6. POPULAR ARIA2C
# ============================================================
print("\n6. Populando aria2c...")

added_coolrom = 0
for serial, url in coolrom_urls.items():
    try:
        filename = unquote(url.split("/")[-1])
        dest = f"{serial}_{filename}"
        mgr.add_uri(url, dest_dir=DOWNLOAD_DIR, filename=dest)
        added_coolrom += 1
    except:
        pass
print(f"   CoolROM: {added_coolrom} URLs adicionadas")

added_archive = 0
for serial, url in archive_urls.items():
    try:
        filename = unquote(url.split("/")[-1])
        dest = f"{serial}_{filename}"
        mgr.add_uri(url, dest_dir=DOWNLOAD_DIR, filename=dest)
        added_archive += 1
    except:
        pass
print(f"   Archive: {added_archive} URLs adicionadas")

# ============================================================
# 7. MONITORAR VELOCIDADE
# ============================================================
print(f"\n7. Monitorando velocidade (60s)...")
print(f"   Total URLs no aria2c: {added_coolrom + added_archive}")

for i in range(6):  # 6 medições de 10s
    time.sleep(10)
    try:
        stat = mgr.get_global_stat()
        speed = int(stat.get("downloadSpeed", 0))
        active = stat.get("numActive")
        waiting = stat.get("numWaiting")
        stopped = stat.get("numStopped")
        speed_mb = speed / 1024 / 1024
        print(f"   [{(i+1)*10}s] speed={speed_mb:.2f}MB/s active={active} waiting={waiting} stopped={stopped}")
    except:
        print(f"   [{(i+1)*10}s] erro ao obter stat")

# Salvar URLs frescas
json.dump(coolrom_urls, open(os.path.join(STATE, "coolrom_jp_fresh_urls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\nURLs frescas salvas em coolrom_jp_fresh_urls.json")
