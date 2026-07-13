"""Pipeline COMPLETO com cookies de sessão do archive.org:
1. Mata TODOS os aria2c (resolve problema de múltiplas instâncias)
2. Limpa arquivos órfãos
3. Reinicia aria2c ÚNICO com --load-cookies
4. Gera URLs frescas coolrom
5. Adiciona TODAS as coleções archive.org (com auth, psx-pal-chd-zstd deve funcionar)
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
COOKIES = {
    "logged-in-sig": "1815424048%201783888048%20NdcQZOzCA4CB%2BcoaGKXMv8yc%2FQ0uKS0DS7NHsVPyFUzCWjdaAjvSnGTdPdq6DwibaBL1t1%2BX001Lp626v%2BnwpQd6OcSm3ooULfGMPlxfQwIWKJWo9cV906yT6IRVmZOrso8y0nUYy%2BiuoC6xLYaXww3uiRYjdElmQJYDarrLK3PEx88JZfG4NXZTXRKvFD74XXWVsftXlRoU6fyfRkPmcExzl9HK1%2FloDawy1Nydw2ChC3v9HMqejk0iqMc0k21ZK0HJs9ofXsmjMnacziSSD1ZgxOKp8uO5AQKtZxlKEplK27uEvzq5PoUsJv7Kfsh7gZp1cilR2sW3c03iP8roGw%3D%3D",
    "logged-in-user": "zaozao2%40gmail.com",
}

# ============================================================
# 0. TESTAR SE COOKIES FUNCIONAM (rápido, antes de tudo)
# ============================================================
print("0. Testando cookies do archive.org...")
try:
    resp = requests.head("https://archive.org/download/psx-pal-chd-zstd/pal/All%20Star%20Boxing%20(Europe).chd",
                        timeout=15, headers=HEADERS, cookies=COOKIES, allow_redirects=True)
    print(f"   psx-pal-chd-zstd COM auth: {resp.status_code} (antes era 403/auth failed)")
    if resp.status_code == 200:
        print("   COOKIES FUNCIONAM! Coleção restrita agora acessível!")
    else:
        print(f"   Ainda com problema. Content-Length={resp.headers.get('Content-Length','?')}")
except Exception as e:
    print(f"   ERRO: {str(e)[:100]}")

# ============================================================
# 1. MATAR TODOS OS ARIA2C
# ============================================================
print("\n1. Matando TODOS os aria2c...")
subprocess.run(["taskkill", "/F", "/IM", "aria2c.exe"], capture_output=True)
time.sleep(3)
# Verificar se morreu
result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq aria2c.exe"], capture_output=True, text=True)
if "aria2c.exe" in result.stdout:
    print("   AINDA RODANDO! Forçando kill...")
    subprocess.run(["taskkill", "/F", "/IM", "aria2c.exe"], capture_output=True)
    time.sleep(3)
print("   OK — todos mortos")

# ============================================================
# 2. LIMPAR ARQUIVOS ÓRFÃOS
# ============================================================
print("\n2. Limpando arquivos órfãos...")
if os.path.exists(DOWNLOAD_DIR):
    removed = 0
    for f in os.listdir(DOWNLOAD_DIR):
        if f.endswith(".aria2"):
            continue
        fp = os.path.join(DOWNLOAD_DIR, f)
        if os.path.isfile(fp) and not os.path.exists(fp + ".aria2"):
            try:
                os.remove(fp)
                removed += 1
            except:
                pass
    print(f"   Removidos: {removed} órfãos")

# Limpar session
open(os.path.join(STATE, "aria2_session.txt"), "w").close()

# ============================================================
# 3. REINICIAR ARIA2C ÚNICO COM COOKIES
# ============================================================
print("\n3. Reiniciando aria2c ÚNICO com cookies...")
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _aria2_manager

mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
mgr.start_daemon()
time.sleep(3)
if not mgr.is_daemon_running():
    print("   ERRO: aria2c não iniciou!")
    sys.exit(1)
print("   aria2c rodando com cookies!")

# ============================================================
# 4. GERAR URLS FRESCAS COOLROM
# ============================================================
print("\n4. Gerando URLs frescas CoolROM...")
coolrom_cache = json.load(open(os.path.join(STATE, "coolrom_cache.json"), "r", encoding="utf-8"))
jp_entries = {k: v for k, v in coolrom_cache.items() if "japan" in k.lower()}

q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
queue = q.get("queue", [])
completed = set(q.get("completed", {}).keys()) if isinstance(q.get("completed"), dict) else set()
failed = set(q.get("failed", {}).keys()) if isinstance(q.get("failed"), dict) else set()
ip = set(q.get("in_progress", {}).keys()) if isinstance(q.get("in_progress"), dict) else set()

jp_pending = {}
eu_pending = {}
us_pending = {}
for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else str(item)
    name = item.get("name", "") if isinstance(item, dict) else ""
    if serial in completed or serial in failed or serial in ip:
        continue
    if serial.startswith(("SLPM", "SLPS", "SLPH", "SCPS", "SIPS")):
        jp_pending[serial] = name
    elif serial.startswith(("SLES", "SCED")):
        eu_pending[serial] = name
    elif serial.startswith(("SLUS", "SCUS")):
        us_pending[serial] = name

print(f"   JP pending: {len(jp_pending)}, EU: {len(eu_pending)}, US: {len(us_pending)}")

# Match fuzzy (JP + EU + US)
def normalize_name(name):
    name = name.lower()
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()

def extract_words(name):
    stop = {'the', 'and', 'for', 'with', 'from', 'vol', 'volume', 'disc', 'japan', 'europe', 'usa'}
    return [w for w in re.findall(r'[a-z0-9]{3,}', name.lower()) if w not in stop]

# Usar TODO o cache (não só JP) para match EU/US também
all_entries = coolrom_cache
cache_normalized = {}
for cache_name, cache_info in all_entries.items():
    norm = normalize_name(cache_name)
    words = set(extract_words(norm))
    if words:
        cache_normalized[cache_name] = {"norm": norm, "words": words, "info": cache_info}

print(f"   Cache normalizado: {len(cache_normalized)} entradas")

all_pending = {**jp_pending, **eu_pending, **us_pending}
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

print(f"   Matches fuzzy: {len(matches)}")

# Buscar URLs frescas em paralelo
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

print(f"   URLs coolrom frescas: {len(coolrom_urls)}")

# ============================================================
# 5. ADICIONAR TODAS AS COLEÇÕES ARCHIVE.ORG (com auth)
# ============================================================
print("\n5. Adicionando URLs archive.org (TODAS coleções, com auth)...")

archive_index = {}
for name in ["archive_name_index.json", "archive_jp_index.json"]:
    p = os.path.join(STATE, name)
    if os.path.exists(p):
        d = json.load(open(p, "r", encoding="utf-8"))
        archive_index.update(d)

# COM auth, todas as coleções devem funcionar
archive_urls = {}
for serial, name in all_pending.items():
    if serial in coolrom_urls:
        continue  # coolrom prioritário
    if serial in archive_index:
        info = archive_index[serial]
        if isinstance(info, dict):
            url = info.get("download_url")
            if not url and info.get("collection") and info.get("file"):
                fname = info["file"].replace(" ", "%20").replace("(", "%28").replace(")", "%29")
                url = f"http://archive.org/download/{info['collection']}/{fname}"
            if url:
                # Converter HTTP para HTTPS (HTTP está bloqueado)
                if url.startswith("http://"):
                    url = "https://" + url[7:]
                archive_urls[serial] = url

print(f"   URLs archive (com auth): {len(archive_urls)}")

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
print(f"   CoolROM: {added_coolrom} URLs")

added_archive = 0
for serial, url in archive_urls.items():
    try:
        filename = unquote(url.split("/")[-1])
        dest = f"{serial}_{filename}"
        mgr.add_uri(url, dest_dir=DOWNLOAD_DIR, filename=dest)
        added_archive += 1
    except:
        pass
print(f"   Archive: {added_archive} URLs")

# ============================================================
# 7. MONITORAR VELOCIDADE (90s)
# ============================================================
print(f"\n7. Monitorando velocidade (90s)...")
print(f"   Total: {added_coolrom + added_archive} URLs no aria2c")

for i in range(9):
    time.sleep(10)
    try:
        stat = mgr.get_global_stat()
        speed = int(stat.get("downloadSpeed", 0))
        active = stat.get("numActive")
        waiting = stat.get("numWaiting")
        stopped = stat.get("numStopped")
        speed_mb = speed / 1024 / 1024
        
        # Contar completos
        completed_count = 0
        if int(stopped) > 0:
            stopped_list = mgr.tell_stopped(0, 100)
            completed_count = sum(1 for d in stopped_list if d.get("status") == "complete")
        
        marker = "✅" if speed_mb >= 20 else ("⚠️" if speed_mb >= 5 else "❌")
        print(f"   [{(i+1)*10:3d}s] {marker} {speed_mb:6.2f}MB/s | active={active} waiting={waiting} stopped={stopped} completed={completed_count}")
    except Exception as e:
        print(f"   [{(i+1)*10}s] erro: {e}")

# Salvar URLs
json.dump(coolrom_urls, open(os.path.join(STATE, "coolrom_fresh_urls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("\nDone!")
