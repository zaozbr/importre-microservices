"""
Busca ROMs JP em collections específicas do archive.org.
Muitos ROMs JP (SLPM/SLPS) estão em collections individuais como ps_xxx.
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
s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')


def advanced_search(query, rows=100):
    url = f"http://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&fl[]=title&fl[]=description&rows={rows}&page=1&output=json"
    try:
        r = s.get(url, timeout=(5, 20))
        if r.status_code == 200:
            return r.json().get('response', {}).get('docs', [])
    except:
        pass
    return []


def get_metadata(identifier):
    url = f"http://archive.org/metadata/{identifier}"
    try:
        r = s.get(url, timeout=(5, 15))
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def search_jp_roms(serial, name=''):
    """Busca ROMs JP com estratégias específicas para SLPM/SLPS."""
    all_results = []

    # Query 1: serial exato
    docs = advanced_search(f'"{serial}"', rows=50)
    for d in docs:
        all_results.append((d, 100))

    # Query 2: serial + psx (muitos items JP têm prefixo psx_)
    docs = advanced_search(f'{serial} psx', rows=50)
    for d in docs:
        all_results.append((d, 90))

    # Query 3: serial + sony playstation
    docs = advanced_search(f'{serial} "sony playstation"', rows=50)
    for d in docs:
        all_results.append((d, 85))

    # Query 4: por nome do jogo (em romaji)
    if name:
        clean = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip()
        if clean and len(clean) > 3:
            # Buscar por partes do nome
            words = clean.split()
            if len(words) >= 2:
                # Primeiras 2 palavras
                partial = ' '.join(words[:2])
                docs = advanced_search(f'"{partial}" playstation japan', rows=50)
                for d in docs:
                    all_results.append((d, 70))

    # Query 5: serial + chd (muitos ROMs JP estão em formato CHD)
    docs = advanced_search(f'{serial} chd', rows=50)
    for d in docs:
        all_results.append((d, 80))

    # Query 6: buscar em collections específicas JP
    docs = advanced_search(f'{serial} AND collection:redump_psx', rows=50)
    for d in docs:
        all_results.append((d, 95))

    # Deduplicar
    seen = set()
    unique = []
    for d, score in all_results:
        ident = d.get('identifier', '')
        if ident and ident not in seen:
            seen.add(ident)
            unique.append((d, score))

    return unique


def resolve_to_url(identifier, serial):
    data = get_metadata(identifier)
    if not data:
        return None, None

    files = data.get('files', [])
    if not files:
        return None, None

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
        return None, None

    candidates.sort(key=lambda x: -x[0])
    best = candidates[0][1]
    url = f"http://archive.org/download/{identifier}/{quote(best, safe='/')}"
    return url, best


def main():
    print("=" * 60, flush=True)
    print("JP ROM SEARCH — busca específica para SLPM/SLPS", flush=True)
    print("=" * 60, flush=True)

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
    for sr, info in failed.items():
        if sr not in seen:
            seen.add(sr)
            to_search.append({'serial': sr, 'name': info.get('name', '')})

    # Filtrar só JP (SLPM, SLPS, SLPS-)
    jp_roms = [item for item in to_search if item.get('serial', '').startswith(('SLPM', 'SLPS'))]
    print(f"Buscando {len(jp_roms)} ROMs JP...\n", flush=True)

    found = []
    for item in jp_roms:
        serial = item.get('serial', '')
        name = item.get('name', '')
        print(f"=== {serial} ({name[:30]}) ===", flush=True)

        results = search_jp_roms(serial, name)
        print(f"  {len(results)} candidatos", flush=True)

        for doc, score in results[:10]:
            ident = doc.get('identifier', '')
            title = doc.get('title', '')
            print(f"  [{score}] {ident} — {title[:50]}", flush=True)

            url, fname = resolve_to_url(ident, serial)
            if url:
                print(f"    -> URL: {url[:80]}", flush=True)
                found.append({
                    'serial': serial, 'name': name, 'url': url,
                    'identifier': ident, 'filename': fname, 'score': score,
                })
                break
        else:
            print(f"  NAO encontrado", flush=True)

    print(f"\n=== RESULTADO ===", flush=True)
    print(f"Encontrados: {len(found)}", flush=True)

    results_path = os.path.join(STATE_DIR, "jp_search_results.json")
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(found, f, ensure_ascii=False, indent=2)
    print(f"Resultados salvos em: {results_path}", flush=True)


if __name__ == '__main__':
    main()
