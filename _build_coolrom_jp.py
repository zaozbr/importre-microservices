"""Constrói cache coolrom para jogos JP buscando por nome.
CoolROM tem jogos JP no site mas o cache atual não os contém.
Varre coolrom.com/roms/psx/ procurando jogos por nome dos pending JP.
"""
import json
import os
import re
import time
import requests
from urllib.parse import quote, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

STATE = r"D:\roms\library\roms\_importre_state"

# Carregar queue
q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
queue = q.get("queue", [])

# Filtrar JP pending
jp_pending = []
for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else str(item)
    name = item.get("name", "") if isinstance(item, dict) else ""
    if serial.startswith(("SLPM", "SLPS", "SLPH", "SCPS", "SIPS")):
        jp_pending.append((serial, name))

print(f"JP pending: {len(jp_pending)}")

# Carregar coolrom_cache existente
cache_path = os.path.join(STATE, "coolrom_cache.json")
cache = json.load(open(cache_path, "r", encoding="utf-8")) if os.path.exists(cache_path) else {}
print(f"Coolrom cache atual: {len(cache)} entradas")

# Verificar quantos JP já estão no cache
jp_in_cache = sum(1 for s, n in jp_pending if s in cache)
print(f"JP no cache: {jp_in_cache}/{len(jp_pending)}")

# Carregar coolrom_index (índice invertido por palavra)
index_path = os.path.join(STATE, "coolrom_index.json")
if os.path.exists(index_path):
    cindex = json.load(open(index_path, "r", encoding="utf-8"))
    print(f"Coolrom index (palavras): {len(cindex)} palavras")
else:
    cindex = {}
    print("Coolrom index: não encontrado")

# Função para buscar jogo no coolrom por nome
def search_coolrom(name, serial):
    """Busca jogo no coolrom pelo nome e retorna URL de download."""
    if not name:
        return None
    
    # Tentar match no índice por palavras
    # Pegar palavras significativas do nome (remover stopwords, números de volume, etc)
    words = re.findall(r'[A-Za-z]{3,}', name.lower())
    if not words:
        return None
    
    # Procurar no índice
    candidates = set()
    for word in words[:3]:  # primeiras 3 palavras significativas
        if word in cindex:
            for entry in cindex[word]:
                candidates.add(entry)
    
    if not candidates:
        return None
    
    # Fazer match fuzzy: verificar se o nome do candidato bate com o nome do jogo
    name_lower = name.lower()
    for candidate in candidates:
        # candidate é "Nome do Jogo (Japan).7z" ou similar
        # Extrair nome sem extensão e sem região
        clean = re.sub(r'\.(7z|zip|rar)$', '', candidate, flags=re.IGNORECASE)
        clean = re.sub(r'\s*\([^)]*\)\s*', '', clean).strip()  # remover (Japan), (Europe), etc
        
        # Match: 60% das palavras devem bater
        clean_words = set(re.findall(r'[A-Za-z]{3,}', clean.lower()))
        name_words = set(re.findall(r'[A-Za-z]{3,}', name_lower))
        
        if not clean_words or not name_words:
            continue
        
        intersection = clean_words & name_words
        overlap = len(intersection) / min(len(clean_words), len(name_words))
        
        if overlap >= 0.6:
            # Encontrou match! Construir URL
            # URL: https://dl.coolrom.com/roms/psx/{filename}/{hash}/{ts}/
            # Mas não temos hash/ts — precisamos da página de detalhe
            return candidate  # retornar nome do arquivo para busca posterior
    
    return None

# Buscar matches
matches = {}
no_match = 0
for serial, name in jp_pending:
    if serial in cache:
        continue  # já no cache
    
    result = search_coolrom(name, serial)
    if result:
        matches[serial] = {"name": name, "coolrom_file": result}
    else:
        no_match += 1

print(f"\nMatches por nome: {len(matches)}")
print(f"Sem match: {no_match}")

# Mostrar amostra
for s, info in list(matches.items())[:10]:
    print(f"  {s}: {info['name'][:40]} -> {info['coolrom_file'][:60]}")

# Salvar matches para uso posterior
matches_path = os.path.join(STATE, "coolrom_jp_matches.json")
json.dump(matches, open(matches_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\nMatches salvos em: {matches_path}")

# Agora buscar URLs reais do coolrom para os matches
# URL: https://coolrom.com/roms/psx/{game-name}/{id}/
# Precisamos buscar a página de detalhe para obter o link dl.coolrom.com

def fetch_coolrom_download_url(game_name):
    """Busca URL de download do coolrom para um jogo."""
    # Normalizar nome para URL
    url_name = game_name.replace(" ", "-").replace("/", "-")
    url_name = re.sub(r'[^A-Za-z0-9\-]', '', url_name)
    
    # Tentar buscar na página de PSX
    search_url = f"https://coolrom.com/roms/psx/"
    try:
        resp = requests.get(search_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        
        # Procurar pelo nome do jogo na página
        # Pattern: <a href="/roms/psx/{name}/{id}/">{display_name}</a>
        pattern = re.compile(r'href="(/roms/pss/[^"]+)"[^>]*>([^<]+)', re.IGNORECASE)
        for m in pattern.finditer(resp.text):
            href, display = m.groups()
            if game_name.lower() in display.lower():
                # Encontrou! Buscar página de detalhe
                detail_url = f"https://coolrom.com{href}"
                detail_resp = requests.get(detail_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                if detail_resp.status_code == 200:
                    # Procurar link dl.coolrom.com
                    dl_pattern = re.compile(r'(https?://dl\.coolrom\.com/[^"\']+)')
                    dl_match = dl_pattern.search(detail_resp.text)
                    if dl_match:
                        return dl_match.group(1)
        return None
    except:
        return None

print(f"\n=== Buscando URLs reais do coolrom (primeiros 20) ===")
found_urls = {}
for serial, info in list(matches.items())[:20]:
    url = fetch_coolrom_download_url(info["coolrom_file"])
    if url:
        found_urls[serial] = url
        print(f"  {serial}: {url[:80]}")
    else:
        print(f"  {serial}: não encontrado")

print(f"\nURLs encontradas: {len(found_urls)}/20")
