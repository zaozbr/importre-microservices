"""Faz match fuzzy dos pending JP com cache coolrom (2941 entradas por nome).
Para cada match, busca URL dl.coolrom.com da página de detalhe em paralelo.
Pré-popula aria2c com todas as URLs encontradas.
"""
import json
import os
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote

STATE = r"D:\roms\library\roms\_importre_state"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. Carregar cache coolrom
coolrom_cache = json.load(open(os.path.join(STATE, "coolrom_cache.json"), "r", encoding="utf-8"))
print(f"Coolrom cache: {len(coolrom_cache)} entradas por nome")

# Filtrar apenas entradas JP (nome contém "japan")
jp_entries = {k: v for k, v in coolrom_cache.items() if "japan" in k.lower()}
print(f"Entradas JP no cache: {len(jp_entries)}")

# 2. Carregar pending JP
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

print(f"JP pending (não processados): {len(jp_pending)}")

# 3. Match fuzzy por nome
def normalize_name(name):
    """Normaliza nome para comparação: lowercase, sem acentos, sem parênteses."""
    name = name.lower()
    name = re.sub(r'\([^)]*\)', '', name)  # remover parênteses
    name = re.sub(r'[^a-z0-9\s]', ' ', name)  # só alfanumérico
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def extract_words(name):
    """Extrai palavras significativas (3+ chars, sem stopwords)."""
    stop = {'the', 'and', 'for', 'with', 'from', 'vol', 'volume', 'disc', 'japan', 'europe', 'usa'}
    words = re.findall(r'[a-z0-9]{3,}', name.lower())
    return [w for w in words if w not in stop]

# Pré-processar cache JP
cache_normalized = {}
for cache_name, cache_info in jp_entries.items():
    norm = normalize_name(cache_name)
    words = set(extract_words(norm))
    if words:
        cache_normalized[cache_name] = {
            "norm": norm,
            "words": words,
            "info": cache_info,
        }

print(f"Cache JP normalizado: {len(cache_normalized)} entradas")

# Fazer match
matches = []
for serial, jp_name in jp_pending.items():
    jp_norm = normalize_name(jp_name)
    jp_words = set(extract_words(jp_norm))
    
    if not jp_words:
        continue
    
    best_match = None
    best_score = 0
    
    for cache_name, cache_data in cache_normalized.items():
        # Score = interseção de palavras / min(palavras)
        intersection = jp_words & cache_data["words"]
        if not intersection:
            continue
        
        score = len(intersection) / max(len(jp_words), len(cache_data["words"]))
        
        if score > best_score:
            best_score = score
            best_match = (cache_name, cache_data["info"])
    
    if best_match and best_score >= 0.5:
        matches.append((serial, jp_name, best_match[0], best_match[1], best_score))

print(f"\nMatches fuzzy (score >= 0.5): {len(matches)}")
for s, n, cn, info, score in sorted(matches, key=lambda x: -x[4])[:15]:
    print(f"  {s}: {n[:30]} -> {cn[:30]} (score={score:.2f})")

# 4. Buscar URLs dl.coolrom.com em paralelo
print(f"\nBuscando URLs dl.coolrom.com para {len(matches)} jogos...")

def fetch_dl_url(detail_info):
    """Busca URL dl.coolrom.com da página de detalhe."""
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
        
        # Às vezes está em JavaScript
        js_pattern = re.compile(r'dl\.coolrom\.com/([^"\'\s<>;]+)')
        m = js_pattern.search(resp.text)
        if m:
            return f"https://dl.coolrom.com/{m.group(1)}"
        
        return None
    except:
        return None

coolrom_dl_urls = {}
with ThreadPoolExecutor(max_workers=15) as executor:
    futures = {}
    for serial, jp_name, cache_name, info, score in matches:
        future = executor.submit(fetch_dl_url, info)
        futures[future] = serial
    
    done = 0
    for future in as_completed(futures):
        serial = futures[future]
        dl_url = future.result()
        done += 1
        if dl_url:
            coolrom_dl_urls[serial] = dl_url
            if done <= 20 or done % 50 == 0:
                print(f"  ✓ [{done}/{len(matches)}] {serial}: {dl_url[:70]}")
        else:
            if done <= 5:
                print(f"  ✗ [{done}/{len(matches)}] {serial}: sem URL")

print(f"\nURLs dl.coolrom.com encontradas: {len(coolrom_dl_urls)}")

# 5. Pré-popular aria2c com URLs do coolrom
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _aria2_manager

mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
if not mgr.is_daemon_running():
    print("Iniciando aria2c...")
    mgr.start_daemon()

# Adicionar URLs do coolrom
download_dir = r"D:\roms\library\roms\_importre_state\downloads"
added = 0
for serial, url in coolrom_dl_urls.items():
    try:
        filename = unquote(url.split("/")[-1])
        dest = f"{serial}_{filename}"
        gid = mgr.add_uri(url, dest_dir=download_dir, filename=dest)
        added += 1
    except Exception as e:
        if added < 3:
            print(f"  ERRO: {e}")

print(f"\nURLs coolrom adicionadas ao aria2c: {added}")

# 6. Adicionar também URLs do archive.org para os que NÃO têm coolrom
archive_index = {}
for name in ["archive_name_index.json", "archive_jp_index.json"]:
    p = os.path.join(STATE, name)
    if os.path.exists(p):
        d = json.load(open(p, "r", encoding="utf-8"))
        archive_index.update(d)

# Construir URLs archive
archive_urls = {}
for serial, jp_name in jp_pending.items():
    if serial in coolrom_dl_urls:
        continue  # já tem coolrom
    if serial in archive_index:
        info = archive_index[serial]
        if isinstance(info, dict):
            if info.get("download_url"):
                archive_urls[serial] = info["download_url"]
            elif info.get("collection") and info.get("file"):
                fname = info["file"].replace(" ", "%20").replace("(", "%28").replace(")", "%29")
                archive_urls[serial] = f"http://archive.org/download/{info['collection']}/{fname}"

print(f"\nURLs archive.org para complementar: {len(archive_urls)}")

added_archive = 0
for serial, url in archive_urls.items():
    try:
        filename = unquote(url.split("/")[-1])
        dest = f"{serial}_{filename}"
        gid = mgr.add_uri(url, dest_dir=download_dir, filename=dest)
        added_archive += 1
    except:
        pass

print(f"URLs archive adicionadas: {added_archive}")

# Estatísticas finais
try:
    stat = mgr.get_global_stat()
    speed = int(stat.get('downloadSpeed', 0))
    print(f"\naria2c: active={stat.get('numActive')} waiting={stat.get('numWaiting')} stopped={stat.get('numStopped')}")
    print(f"  downloadSpeed: {speed/1024/1024:.2f}MB/s ({speed/1024:.0f}KB/s)")
except:
    pass

# Salvar URLs para uso futuro
json.dump(coolrom_dl_urls, open(os.path.join(STATE, "coolrom_jp_dl_urls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\nURLs salvas em coolrom_jp_dl_urls.json")
