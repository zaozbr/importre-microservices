"""
Busca profunda no archive.org: usar advancedsearch API com várias queries
para encontrar ROMs que não estão nas collections redump padrão.
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
    url = f"http://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&fl[]=title&fl[]=description&fl[]=collection&rows={rows}&page=1&output=json"
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


def search_rom_deep(serial, name=''):
    """Busca profunda com múltiplas queries."""
    all_results = []

    # Query 1: serial exato entre aspas
    docs = advanced_search(f'"{serial}"', rows=50)
    for d in docs:
        all_results.append((d, 100))

    # Query 2: serial sem hífen
    serial_nohyphen = serial.replace('-', ' ')
    docs = advanced_search(f'{serial_nohyphen} playstation', rows=50)
    for d in docs:
        all_results.append((d, 80))

    # Query 3: serial + collection sony_playstation
    docs = advanced_search(f'{serial} AND collection:sony_playstation', rows=50)
    for d in docs:
        all_results.append((d, 90))

    # Query 4: por nome do jogo
    if name:
        clean = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip()
        if clean and len(clean) > 3:
            docs = advanced_search(f'"{clean}" playstation', rows=50)
            for d in docs:
                all_results.append((d, 70))

    # Query 5: serial + mediatype
    docs = advanced_search(f'{serial} AND mediatype:software', rows=50)
    for d in docs:
        all_results.append((d, 85))

    # Query 6: serial + mediatype texts (alguns ROMs estão como texts)
    docs = advanced_search(f'{serial} AND mediatype:texts', rows=50)
    for d in docs:
        all_results.append((d, 85))

    # Deduplicar por identifier
    seen = set()
    unique = []
    for d, score in all_results:
        ident = d.get('identifier', '')
        if ident and ident not in seen:
            seen.add(ident)
            unique.append((d, score))

    return unique


def resolve_and_get_url(identifier, serial):
    """Busca metadata e encontra arquivo ROM."""
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
    print("DEEP ARCHIVE SEARCH — múltiplas queries no archive.org", flush=True)
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

    print(f"Buscando {len(to_search)} ROMs com queries profundas...\n", flush=True)

    found = []
    for item in to_search:
        serial = item.get('serial', '')
        name = item.get('name', '')
        print(f"=== {serial} ({name[:30]}) ===", flush=True)

        results = search_rom_deep(serial, name)
        print(f"  {len(results)} candidatos", flush=True)

        best_url = None
        best_fname = None
        best_ident = None

        for doc, score in results[:15]:
            ident = doc.get('identifier', '')
            title = doc.get('title', '')
            print(f"  [{score}] {ident} — {title[:50]}", flush=True)

            url, fname = resolve_and_get_url(ident, serial)
            if url:
                best_url = url
                best_fname = fname
                best_ident = ident
                print(f"    -> URL: {url[:80]}", flush=True)
                break

        if best_url:
            found.append({
                'serial': serial, 'name': name, 'url': best_url,
                'identifier': best_ident, 'filename': best_fname,
            })
        else:
            print(f"  NAO encontrado", flush=True)

    print(f"\n=== RESULTADO ===", flush=True)
    print(f"Encontrados: {len(found)}", flush=True)

    results_path = os.path.join(STATE_DIR, "deep_archive_results.json")
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(found, f, ensure_ascii=False, indent=2)
    print(f"Resultados salvos em: {results_path}", flush=True)


if __name__ == '__main__':
    main()
