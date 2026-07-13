"""Faz scraping da lista de jogos JP do coolrom.
URL: https://coolrom.com/roms/psx/japan/
Padrão: /roms/psx/{id}/{Name}.php
"""
import json
import os
import re
import time
import requests
from urllib.parse import unquote

STATE = r"D:\roms\library\roms\_importre_state"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. Buscar página JP do coolrom
print("Buscando lista de jogos JP do coolrom...")
all_jp_games = {}  # name -> (id, detail_url)

# Página JP tem paginação por letra: /roms/psx/japan/{letter}/
# Ou números: /roms/psx/japan/0/
letters = list("0ABCDEFGHIJKLMNOPQRSTUVWXYZ")

for letter in letters:
    url = f"https://coolrom.com/roms/psx/japan/{letter}/"
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        if resp.status_code != 200:
            print(f"  {letter}: HTTP {resp.status_code}")
            continue
        
        # Pattern: <a href="/roms/psx/{id}/{Name}.php">{Display Name}</a>
        pattern = re.compile(r'href="(/roms/psx/(\d+)/([^"]+)\.php)"[^>]*>([^<]+)</a>')
        matches = pattern.findall(resp.text)
        
        for href, game_id, slug, display_name in matches:
            display_name = display_name.strip()
            # Ignorar links de navegação (Top ROMs, etc)
            if not display_name or len(display_name) < 2:
                continue
            if display_name in ("Top ROMs", "All", "Australia", "Europe", "France", 
                                "Germany", "Italy", "Japan", "Russia", "Spain"):
                continue
            
            all_jp_games[display_name.lower()] = {
                "id": game_id,
                "slug": slug,
                "display": display_name,
                "href": href,
            }
        
        print(f"  {letter}: {len(matches)} jogos")
        time.sleep(0.3)
    except Exception as e:
        print(f"  {letter}: ERRO — {e}")

print(f"\nTotal jogos JP no coolrom: {len(all_jp_games)}")

# 2. Carregar pending JP
q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
queue = q.get("queue", [])
jp_pending = {}
for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else str(item)
    name = item.get("name", "") if isinstance(item, dict) else ""
    if serial.startswith(("SLPM", "SLPS", "SLPH", "SCPS", "SIPS")):
        jp_pending[serial] = name

print(f"JP pending: {len(jp_pending)}")

# 3. Fazer match
matches = []
for serial, jp_name in jp_pending.items():
    jp_name_lower = jp_name.lower()
    
    # Match exato
    if jp_name_lower in all_jp_games:
        matches.append((serial, jp_name, all_jp_games[jp_name_lower], "exact"))
        continue
    
    # Match por palavras (primeiras 2-3 palavras significativas)
    jp_words = re.findall(r'[A-Za-z]{3,}', jp_name_lower)
    if not jp_words:
        continue
    
    search_key = " ".join(jp_words[:3])
    best_match = None
    best_score = 0
    
    for cool_name, cool_info in all_jp_games.items():
        if search_key in cool_name:
            # Score = quantas palavras batem
            cool_words = set(re.findall(r'[A-Za-z]{3,}', cool_name))
            jp_word_set = set(jp_words)
            score = len(cool_words & jp_word_set) / max(len(jp_word_set), 1)
            if score > best_score:
                best_score = score
                best_match = cool_info
    
    if best_match and best_score >= 0.4:
        matches.append((serial, jp_name, best_match, f"partial:{best_score:.1f}"))

print(f"\nMatches: {len(matches)}")
for s, n, info, m in matches[:15]:
    print(f"  {s}: {n[:35]} -> {info['display'][:35]} ({m})")

# 4. Buscar URLs de download reais (dl.coolrom.com)
print(f"\nBuscando URLs de download para {len(matches)} matches...")

def fetch_dl_url(detail_href):
    """Busca URL dl.coolrom.com da página de detalhe."""
    url = f"https://coolrom.com{detail_href}"
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        if resp.status_code != 200:
            return None
        
        # Procurar por link dl.coolrom.com
        # Pattern: <a href="https://dl.coolrom.com/..."> ou form action
        dl_pattern = re.compile(r'(https?://dl\.coolrom\.com/[^"\'\s<>]+)')
        m = dl_pattern.search(resp.text)
        if m:
            return m.group(1)
        
        # Às vezes está em JavaScript: window.location = "dl.coolrom.com/..."
        js_pattern = re.compile(r'dl\.coolrom\.com/([^"\'\s<>;]+)')
        m = js_pattern.search(resp.text)
        if m:
            return f"https://dl.coolrom.com/{m.group(1)}"
        
        return None
    except:
        return None

coolrom_urls = {}
for serial, name, info, match_type in matches:
    dl_url = fetch_dl_url(info["href"])
    if dl_url:
        coolrom_urls[serial] = dl_url
        print(f"  ✓ {serial}: {dl_url[:80]}")
    else:
        print(f"  ✗ {serial}: sem URL dl")
    time.sleep(0.2)  # não sobrecarregar

print(f"\nURLs coolrom JP encontradas: {len(coolrom_urls)}")

# 5. Atualizar cache
cache_path = os.path.join(STATE, "coolrom_cache.json")
coolrom_cache = json.load(open(cache_path, "r", encoding="utf-8")) if os.path.exists(cache_path) else {}
added = 0
for serial, url in coolrom_urls.items():
    if serial not in coolrom_cache:
        coolrom_cache[serial] = url
        added += 1

json.dump(coolrom_cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\nCoolrom cache: {len(coolrom_cache)} entradas (+{added} novas JP)")

# Salvar lista JP completa para uso futuro
json.dump(all_jp_games, open(os.path.join(STATE, "coolrom_jp_list.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Lista JP completa salva: {len(all_jp_games)} jogos")
