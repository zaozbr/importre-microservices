"""Busca diretamente no coolrom.com jogos JP por nome.
Faz scraping da lista de PSX e busca por nome dos pending JP.
"""
import json
import os
import re
import time
import requests
from urllib.parse import quote, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

STATE = r"D:\roms\library\roms\_importre_state"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. Carregar pending JP
q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
queue = q.get("queue", [])
jp_pending = {}
for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else str(item)
    name = item.get("name", "") if isinstance(item, dict) else ""
    if serial.startswith(("SLPM", "SLPS", "SLPH", "SCPS", "SIPS")):
        jp_pending[serial] = name

print(f"JP pending: {len(jp_pending)}")

# 2. Fazer scraping da lista de PSX do coolrom
# A lista tem páginas: coolrom.com/roms/psx/?page=1, ?page=2, etc
# Ou lista alfabética: coolrom.com/roms/psx/?letter=A

print("\nBuscando lista de jogos PSX do coolrom...")

# Tentar página principal primeiro
all_games = {}  # name -> detail_url

for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    url = f"https://coolrom.com/roms/psx/?letter={letter}"
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        if resp.status_code != 200:
            continue
        
        # Pattern: <a href="/roms/psx/{slug}/{id}/">{name}</a>
        # Ou: <a href="https://coolrom.com/roms/psx/{slug}/{id}/">
        pattern = re.compile(r'href="(?:https?://coolrom\.com)?(/roms/psx/[^"]+/)"[^>]*>([^<]+)</a>', re.IGNORECASE)
        matches = pattern.findall(resp.text)
        
        for href, name in matches:
            name = name.strip()
            if name and len(name) > 2 and not name.startswith("<"):
                all_games[name.lower()] = href
        
        print(f"  Letra {letter}: {len(matches)} jogos")
        time.sleep(0.3)  # não sobrecarregar
    except Exception as e:
        print(f"  Letra {letter}: ERRO — {e}")

print(f"\nTotal jogos no coolrom PSX: {len(all_games)}")

# 3. Fazer match dos pending JP com a lista do coolrom
matches = []
for serial, jp_name in jp_pending.items():
    jp_name_lower = jp_name.lower()
    
    # Tentar match exato
    if jp_name_lower in all_games:
        matches.append((serial, jp_name, all_games[jp_name_lower], "exact"))
        continue
    
    # Tentar match parcial (primeiras palavras)
    jp_words = re.findall(r'[A-Za-z]{3,}', jp_name_lower)
    if not jp_words:
        continue
    
    # Procurar jogos que contenham as primeiras 2-3 palavras
    search_key = " ".join(jp_words[:3])
    for cool_name, cool_url in all_games.items():
        if search_key in cool_name:
            matches.append((serial, jp_name, cool_url, f"partial:{search_key}"))
            break

print(f"\nMatches: {len(matches)}")
for s, n, u, m in matches[:10]:
    print(f"  {s}: {n[:40]} -> {u} ({m})")

# 4. Para cada match, buscar URL de download real (dl.coolrom.com)
print(f"\nBuscando URLs de download para {len(matches)} matches...")

def fetch_dl_url(detail_path):
    """Busca URL de download dl.coolrom.com da página de detalhe."""
    url = f"https://coolrom.com{detail_path}"
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        if resp.status_code != 200:
            return None
        
        # Procurar link dl.coolrom.com
        dl_pattern = re.compile(r'(https?://dl\.coolrom\.com/[^"\'\s<>]+)')
        m = dl_pattern.search(resp.text)
        if m:
            return m.group(1)
        
        # Às vezes o link está em JavaScript ou data attribute
        dl_pattern2 = re.compile(r'dl\.coolrom\.com/([^"\'\s<>]+)')
        m = dl_pattern2.search(resp.text)
        if m:
            return f"https://dl.coolrom.com/{m.group(1)}"
        
        return None
    except:
        return None

# Buscar em paralelo
coolrom_urls = {}
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {}
    for serial, name, url, match_type in matches:
        future = executor.submit(fetch_dl_url, url)
        futures[future] = (serial, name, url)
    
    for future in as_completed(futures):
        serial, name, url = futures[future]
        dl_url = future.result()
        if dl_url:
            coolrom_urls[serial] = {"name": name, "url": dl_url, "detail": url}
            print(f"  ✓ {serial}: {dl_url[:80]}")
        else:
            print(f"  ✗ {serial}: sem URL dl")

print(f"\nURLs coolrom encontradas: {len(coolrom_urls)}")

# 5. Salvar e atualizar cache
coolrom_cache = json.load(open(os.path.join(STATE, "coolrom_cache.json"), "r", encoding="utf-8")) if os.path.exists(os.path.join(STATE, "coolrom_cache.json")) else {}
for serial, info in coolrom_urls.items():
    coolrom_cache[serial] = info["url"]

json.dump(coolrom_cache, open(os.path.join(STATE, "coolrom_cache.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\nCoolrom cache atualizado: {len(coolrom_cache)} entradas (+{len(coolrom_urls)} novas)")

# Salvar matches completos
json.dump(coolrom_urls, open(os.path.join(STATE, "coolrom_jp_urls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
