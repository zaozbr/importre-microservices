"""
Busca os 325 ROMs não encontrados pelo cross_index.
Usa advancedsearch com cookies (acesso completo) e busca por nome em todas as coleções.
Também busca em coleções individuais (psx_xxx) que podem ter os ROMs.
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

STATE_DIR = r'D:\roms\library\roms\_importre_state'
RESULTS_PATH = os.path.join(STATE_DIR, 'deep_search_v2_results.json')
ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')

# Cookies do archive.org
COOKIES = {
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
}

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
s.cookies.update(COOKIES)


def advanced_search(query, rows=100):
    url = f"http://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&fl[]=title&rows={rows}&page=1&output=json"
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


def normalize_name(name):
    name = name.lower()
    replacements = {'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a',
                    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
                    'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
                    'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
                    'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
                    'ç': 'c', 'ñ': 'n'}
    for k, v in replacements.items():
        name = name.replace(k, v)
    name = re.sub(r'[^\w\s]', ' ', name)
    stop_words = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for',
                  'and', 'or', 'vol', 'series', 'psx', 'ps1', 'playstation',
                  'usa', 'europe', 'japan', 'pal', 'ntsc', 'disc', 'iso',
                  'bin', 'cue', 'zip', '7z', 'chd', 'rev', 'v1', 'v2'}
    words = [w for w in name.split() if w and w not in stop_words and len(w) > 1]
    return ' '.join(words)


def search_rom_deep(serial, name=''):
    """Busca profunda com múltiplas estratégias."""
    all_ids = []

    # Query 1: serial exato
    docs = advanced_search(f'"{serial}"', rows=100)
    all_ids.extend([(d['identifier'], 100) for d in docs if 'identifier' in d])

    # Query 2: serial + playstation
    docs = advanced_search(f'{serial} playstation', rows=50)
    all_ids.extend([(d['identifier'], 85) for d in docs if 'identifier' in d])

    # Query 3: serial + mediatype software
    docs = advanced_search(f'{serial} AND mediatype:software', rows=50)
    all_ids.extend([(d['identifier'], 90) for d in docs if 'identifier' in d])

    # Query 4: por nome do jogo
    if name:
        clean = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip()
        if clean and len(clean) > 3:
            words = [w for w in clean.split() if len(w) > 2]
            if words:
                partial = ' '.join(words[:3])
                docs = advanced_search(f'"{partial}" playstation', rows=50)
                all_ids.extend([(d['identifier'], 70) for d in docs if 'identifier' in d])

    # Query 5: serial sem hifen
    serial_no = serial.replace('-', ' ')
    docs = advanced_search(f'{serial_no}', rows=50)
    all_ids.extend([(d['identifier'], 75) for d in docs if 'identifier' in d])

    # Deduplicar mantendo maior score
    best = {}
    for ident, score in all_ids:
        if ident not in best or score > best[ident]:
            best[ident] = score

    return sorted(best.items(), key=lambda x: -x[1])


def resolve_to_url(identifier, serial, name=''):
    """Busca metadata e encontra arquivo ROM."""
    data = get_metadata(identifier)
    if not data:
        return None, None, None

    files = data.get('files', [])
    if not files:
        return None, None, None

    serial_lower = serial.lower().replace('-', '')
    serial_underscore = serial.lower().replace('-', '_')
    norm_name = normalize_name(name)

    candidates = []
    for f in files:
        fname = f.get('name', '')
        fname_lower = fname.lower()
        if not any(fname_lower.endswith(ext) for ext in ROM_EXTS):
            continue
        score = 0
        fname_normalized = fname_lower.replace('-', '').replace('_', '').replace(' ', '')
        if serial_lower in fname_normalized:
            score = 100
        elif serial_underscore in fname_lower:
            score = 80
        elif serial.lower() in fname_lower:
            score = 60
        # Match por nome
        if norm_name and score == 0:
            fname_norm = normalize_name(fname)
            if fname_norm == norm_name:
                score = 90
            elif norm_name and all(w in fname_norm for w in norm_name.split()[:2]):
                score = 70
        if fname_lower.endswith(('.zip', '.7z', '.chd')):
            score += 5
        try:
            size = int(f.get('size', '0'))
            if size > 5 * 1024 * 1024:
                score += 5
            elif size < 1024 * 1024:
                score -= 20
        except:
            pass
        candidates.append((score, fname, f.get('size', '0')))

    if not candidates:
        for f in files:
            fname = f.get('name', '')
            if any(fname.lower().endswith(ext) for ext in ROM_EXTS):
                candidates.append((0, fname, f.get('size', '0')))
                break

    if not candidates:
        return None, None, None

    candidates.sort(key=lambda x: -x[0])
    best_score, best_fname, best_size = candidates[0]

    if best_score < 20:
        return None, None, None

    url = f"http://archive.org/download/{identifier}/{quote(best_fname, safe='/')}"
    return url, best_fname, best_size


def search_one_rom(serial, name):
    """Busca um ROM e retorna resultado completo."""
    results = search_rom_deep(serial, name)

    for ident, score in results[:20]:
        url, fname, size = resolve_to_url(ident, serial, name)
        if url:
            return {
                'serial': serial,
                'name': name,
                'identifier': ident,
                'url': url,
                'filename': fname,
                'size': size,
                'score': score,
            }
    return None


def main():
    print("=" * 70, flush=True)
    print("DEEP SEARCH V2 — buscando ROMs nao encontrados (com cookies)", flush=True)
    print("=" * 70, flush=True)

    # Carregar faltantes
    with open(os.path.join(STATE_DIR, 'missing_analysis.json'), 'r', encoding='utf-8') as f:
        analysis = json.load(f)
    missing = analysis.get('missing_commercial', {})

    # Carregar nao encontrados pelo cross_index
    with open(os.path.join(STATE_DIR, 'cross_index_results.json'), 'r', encoding='utf-8') as f:
        cross = json.load(f)
    cross_not_found = set(cross.get('not_found', []))

    # Carregar ja encontrados pelo mega_search
    mega_found = set()
    if os.path.exists(os.path.join(STATE_DIR, 'mega_search_results.json')):
        with open(os.path.join(STATE_DIR, 'mega_search_results.json'), 'r', encoding='utf-8') as f:
            mega = json.load(f)
            mega_found = {r['serial'] for r in mega.get('found', [])}

    # ROMs para buscar = nao encontrados pelo cross_index E nao encontrados pelo mega_search
    to_search = {s: missing[s] for s in cross_not_found if s in missing and s not in mega_found}

    print(f"Para buscar: {len(to_search)}\n", flush=True)

    # Carregar resultados anteriores
    found = []
    not_found = []
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, 'r', encoding='utf-8') as f:
            prev = json.load(f)
            found = prev.get('found', [])
            not_found = prev.get('not_found', [])

    found_serials = {r['serial'] for r in found}
    remaining = {s: n for s, n in to_search.items() if s not in found_serials and s not in not_found}

    print(f"Restantes: {len(remaining)}\n", flush=True)

    # Buscar em paralelo
    batch_size = 50
    all_items = list(remaining.items())

    for batch_start in range(0, len(all_items), batch_size):
        batch = all_items[batch_start:batch_start + batch_size]
        print(f"\n--- Batch {batch_start//batch_size + 1} ---", flush=True)

        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(search_one_rom, serial, name): serial for serial, name in batch}
            for f in as_completed(futures):
                serial = futures[f]
                try:
                    result = f.result()
                    if result:
                        found.append(result)
                        print(f"  [OK] {serial}: {result['identifier']} -> {result['filename'][:40]}", flush=True)
                    else:
                        not_found.append(serial)
                        print(f"  [--] {serial}", flush=True)
                except Exception as e:
                    not_found.append(serial)
                    print(f"  [ER] {serial}: {e}", flush=True)

        with open(RESULTS_PATH, 'w', encoding='utf-8') as f:
            json.dump({'found': found, 'not_found': not_found}, f, ensure_ascii=False, indent=2)

    print(f"\n=== RESULTADO ===", flush=True)
    print(f"Encontrados: {len(found)}", flush=True)
    print(f"Nao encontrados: {len(not_found)}", flush=True)


if __name__ == '__main__':
    main()
