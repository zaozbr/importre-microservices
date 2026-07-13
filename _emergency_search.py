"""
EMERGENCIA: Busca os 325 ROMs nao encontrados em TODO o archive.org.
Estrategia: advancedsearch por serial em todas as colecoes (nao so Redump).
Muitos ROMs podem estar em uploads individuais ou outras colecoes.
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
RESULTS_PATH = os.path.join(STATE_DIR, 'emergency_search_results.json')
ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')

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
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            return r.json().get('response', {}).get('docs', [])
    except:
        pass
    return []


def get_metadata(identifier):
    url = f"http://archive.org/metadata/{identifier}"
    try:
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def extract_serial(text):
    match = re.search(r'(S[LC][EUP]S?-\d{4,5}|SCUS-\d{5})', text.upper())
    return match.group(1) if match else None


def search_one_rom(serial, name):
    """Busca um ROM em todo o archive.org."""
    all_ids = []

    # Query 1: serial exato entre aspas
    docs = advanced_search(f'"{serial}"', rows=100)
    all_ids.extend([(d['identifier'], 100) for d in docs if 'identifier' in d])

    # Query 2: serial sem hifen
    serial_no_dash = serial.replace('-', '')
    docs = advanced_search(f'{serial_no_dash} playstation', rows=50)
    all_ids.extend([(d['identifier'], 80) for d in docs if 'identifier' in d])

    # Query 3: serial + mediatype software
    docs = advanced_search(f'{serial} AND mediatype:software', rows=50)
    all_ids.extend([(d['identifier'], 90) for d in docs if 'identifier' in d])

    # Query 4: por nome do jogo (primeiras palavras)
    if name:
        clean = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip()
        if clean and len(clean) > 3:
            words = [w for w in clean.split() if len(w) > 2]
            if words:
                partial = ' '.join(words[:3])
                docs = advanced_search(f'"{partial}" playstation', rows=50)
                all_ids.extend([(d['identifier'], 60) for d in docs if 'identifier' in d])

    # Deduplicar
    best = {}
    for ident, score in all_ids:
        if ident not in best or score > best[ident]:
            best[ident] = score

    # Resolver cada identificador
    for ident, score in sorted(best.items(), key=lambda x: -x[1])[:15]:
        data = get_metadata(ident)
        if not data:
            continue

        files = data.get('files', [])
        if not files:
            continue

        serial_lower = serial.lower().replace('-', '')
        serial_underscore = serial.lower().replace('-', '_')

        candidates = []
        for f in files:
            fname = f.get('name', '')
            fname_lower = fname.lower()
            if not any(fname_lower.endswith(ext) for ext in ROM_EXTS):
                continue
            file_score = 0
            fname_normalized = fname_lower.replace('-', '').replace('_', '').replace(' ', '')
            if serial_lower in fname_normalized:
                file_score = 100
            elif serial_underscore in fname_lower:
                file_score = 80
            elif serial.lower() in fname_lower:
                file_score = 60
            if fname_lower.endswith(('.zip', '.7z', '.chd')):
                file_score += 5
            try:
                size = int(f.get('size', '0'))
                if size > 5 * 1024 * 1024:
                    file_score += 5
                elif size < 1024 * 1024:
                    file_score -= 20
            except:
                pass
            candidates.append((file_score, fname, f.get('size', '0')))

        if not candidates:
            continue

        candidates.sort(key=lambda x: -x[0])
        best_file_score, best_fname, best_size = candidates[0]

        if best_file_score >= 20:
            url = f"http://archive.org/download/{ident}/{quote(best_fname, safe='/')}"
            return {
                'serial': serial,
                'name': name,
                'identifier': ident,
                'url': url,
                'filename': best_fname,
                'size': best_size,
                'score': score,
            }

    return None


def main():
    print("=" * 70, flush=True)
    print("EMERGENCY SEARCH — buscando 325 ROMs em TODO archive.org", flush=True)
    print("=" * 70, flush=True)

    # Carregar faltantes
    with open(os.path.join(STATE_DIR, 'missing_analysis.json'), 'r', encoding='utf-8') as f:
        analysis = json.load(f)
    missing = analysis.get('missing_commercial', {})

    # Carregar nao encontrados pelo cross_index
    with open(os.path.join(STATE_DIR, 'cross_index_results.json'), 'r', encoding='utf-8') as f:
        cross = json.load(f)
    cross_found = {r['serial'] for r in cross.get('found', [])}
    cross_not_found = set(cross.get('not_found', []))

    # Carregar ja encontrados pelo mega_download
    with open(QUEUE_PATH := os.path.join(STATE_DIR, 'queue.json'), 'r', encoding='utf-8') as f:
        q = json.load(f)
    completed = q.get('completed', {})
    if not isinstance(completed, dict):
        completed = {}

    to_search = {s: missing[s] for s in cross_not_found if s in missing and s not in completed}
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

    # Buscar em paralelo (15 threads)
    batch_size = 50
    all_items = list(remaining.items())

    for batch_start in range(0, len(all_items), batch_size):
        batch = all_items[batch_start:batch_start + batch_size]
        print(f"\n--- Batch {batch_start//batch_size + 1}/{(len(all_items)-1)//batch_size + 1} ---", flush=True)

        with ThreadPoolExecutor(max_workers=15) as ex:
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
