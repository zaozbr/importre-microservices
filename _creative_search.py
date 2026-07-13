"""
Buscador criativo de ROMs PSX no archive.org.
Estrategias:
1. Busca na API advancedsearch por serial (multi-query)
2. Busca por nome do jogo
3. Busca em collections CHD/redump conhecidas
4. Cache de metadata
"""
import sys, os, time, json, re
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r"D:\roms\library\roms\_importre_state"
CACHE_PATH = os.path.join(STATE_DIR, "archive_cache.json")

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')


def archive_search_api(query, rows=50):
    url = f"http://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&fl[]=title&fl[]=description&rows={rows}&page=1&output=json"
    try:
        r = s.get(url, timeout=(5, 15))
        if r.status_code == 200:
            return r.json().get('response', {}).get('docs', [])
    except:
        pass
    return []


def archive_metadata(identifier):
    url = f"http://archive.org/metadata/{identifier}"
    try:
        r = s.get(url, timeout=(5, 15))
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def search_serial_creative(serial, name=''):
    """Busca criativa por um ROM. Retorna lista de (identifier, title, url, score)."""
    results = []

    # Estrategia 1: Busca exata por serial entre aspas
    queries = [
        f'"{serial}"',
        f'{serial} mediatype:software',
        f'{serial} mediatype:texts',
    ]

    # Estrategia 2: Busca por nome (se tiver)
    if name:
        # Limpar nome: remover [RERELEASE], parenteses, etc
        clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip()
        if clean_name and len(clean_name) > 3:
            queries.append(f'"{clean_name}" playstation')
            queries.append(f'{clean_name} psx')

    # Estrategia 3: Busca por prefixo do serial (SLUS -> NTSC-U, SLES -> PAL, SLPS -> Japan)
    prefix = serial[:4]
    queries.append(f'{serial} AND collection:sony_playstation')

    for q in queries:
        docs = archive_search_api(q, rows=30)
        for doc in docs:
            ident = doc.get('identifier', '')
            title = doc.get('title', '')
            desc = doc.get('description', '')

            # Score
            score = 0
            sl = serial.lower().replace('-', '')
            if sl in ident.lower().replace('-', '').replace('_', '').replace(' ', ''):
                score = 100
            elif serial.lower() in ident.lower():
                score = 80
            elif serial.lower() in title.lower():
                score = 70
            elif serial.lower() in desc.lower():
                score = 50
            elif name and name.lower()[:20] in title.lower():
                score = 40

            if score > 0:
                results.append((ident, title, score))

    # Deduplicar e ordenar
    seen = set()
    unique = []
    for ident, title, score in sorted(results, key=lambda x: -x[2]):
        if ident not in seen:
            seen.add(ident)
            unique.append((ident, title, score))

    return unique


def resolve_to_url(identifier, serial):
    """Dado um identifier, encontra o arquivo ROM e retorna URL direta."""
    data = archive_metadata(identifier)
    if not data:
        return None

    files = data.get('files', [])
    if not files:
        return None

    serial_lower = serial.lower().replace('-', '')
    serial_underscore = serial.lower().replace('-', '_')

    candidates = []
    for f in files:
        fname = f.get('name', '')
        fname_lower = fname.lower()
        if not any(fname_lower.endswith(ext) for ext in ROM_EXTS):
            continue
        score = 0
        if serial_lower in fname_lower.replace('-', '').replace('_', '').replace(' ', ''):
            score = 100
        elif serial_underscore in fname_lower:
            score = 80
        elif serial_lower in fname_lower:
            score = 60
        if fname_lower.endswith(('.zip', '.7z', '.chd')):
            score += 10
        candidates.append((score, fname))

    if not candidates:
        for f in files:
            fname = f.get('name', '')
            if any(fname.lower().endswith(ext) for ext in ROM_EXTS):
                candidates.append((0, fname))
                break

    if not candidates:
        return None

    candidates.sort(key=lambda x: -x[0])
    best = candidates[0][1]
    return f"http://archive.org/download/{identifier}/{quote(best, safe='/')}"


def search_and_resolve(serial, name=''):
    """Busca e resolve para URL. Retorna (url, identifier) ou (None, None)."""
    results = search_serial_creative(serial, name)
    for ident, title, score in results[:10]:
        url = resolve_to_url(ident, serial)
        if url:
            return url, ident
    return None, None


def main():
    """Testa busca criativa nos ROMs pendentes."""
    QUEUE_PATH = os.path.join(STATE_DIR, "queue.json")
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)

    pending = q.get('queue', [])
    completed = q.get('completed', {})
    if not isinstance(completed, dict):
        completed = {}
    failed = q.get('failed', {})
    if not isinstance(failed, dict):
        failed = {}

    seen = set()
    to_search = []
    for item in pending:
        if isinstance(item, dict):
            sr = item.get('serial', '')
            if sr and sr not in seen and sr not in completed:
                seen.add(sr)
                to_search.append(item)

    print(f"Buscando {len(to_search)} ROMs com busca criativa...\n")

    for item in to_search:
        serial = item.get('serial', '')
        name = item.get('name', '')
        print(f"=== {serial} ({name[:40]}) ===")
        url, ident = search_and_resolve(serial, name)
        if url:
            print(f"  ENCONTRADO: {ident}")
            print(f"  URL: {url[:100]}")
        else:
            print(f"  NAO encontrado")


if __name__ == '__main__':
    main()
