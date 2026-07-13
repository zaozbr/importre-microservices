"""
EMERGENCIA: Indexa colecoes adicionais do archive.org que podem ter os 325 ROMs.
Busca por colecoes com "psx" ou "playstation" no nome e indexa todas.
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
EXTRA_INDEX_PATH = os.path.join(STATE_DIR, 'extra_index.json')

COOKIES = {
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
}

ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
s.cookies.update(COOKIES)


def advanced_search(query, rows=1000):
    url = f"http://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&fl[]=title&rows={rows}&page=1&output=json"
    try:
        r = s.get(url, timeout=30)
        if r.status_code == 200:
            return r.json().get('response', {}).get('docs', [])
    except:
        pass
    return []


def extract_serial(text):
    match = re.search(r'(S[LC][EUP]S?-\d{4,5}|SCUS-\d{5})', text.upper())
    return match.group(1) if match else None


def index_collection(identifier):
    url = f'http://archive.org/metadata/{identifier}'
    try:
        r = s.get(url, timeout=30)
        if r.status_code != 200:
            return identifier, []
        data = r.json()
        files = data.get('files', [])
        entries = []
        for f in files:
            fname = f.get('name', '')
            if not any(fname.lower().endswith(ext) for ext in ROM_EXTS):
                continue
            serial = extract_serial(fname)
            if not serial:
                title = data.get('metadata', {}).get('title', '')
                serial = extract_serial(title)
            size = f.get('size', '0')
            entries.append({
                'serial': serial,
                'filename': fname,
                'size': size,
                'collection': identifier,
            })
        return identifier, entries
    except:
        return identifier, []


def main():
    print("=" * 70, flush=True)
    print("INDEX EXTRA — buscando colecoes PSX adicionais", flush=True)
    print("=" * 70, flush=True)

    # Carregar indice existente para saber o que ja temos
    with open(os.path.join(STATE_DIR, 'smart_index.json'), 'r', encoding='utf-8') as f:
        index = json.load(f)

    existing_colls = set()
    for entries in index.get('by_serial', {}).values():
        for e in entries:
            existing_colls.add(e['collection'])
    for entries in index.get('by_name', {}).values():
        for e in entries:
            existing_colls.add(e['collection'])

    # Tambem carregar all_redump_collections
    with open(os.path.join(STATE_DIR, 'all_redump_collections.json'), 'r') as f:
        redump_colls = json.load(f)
    existing_colls.update(redump_colls)

    print(f"Colecoes ja conhecidas: {len(existing_colls)}", flush=True)

    # Buscar colecoes com psx/playstation no identifier
    queries = [
        'identifier:psx* AND mediatype:software',
        'identifier:playstation* AND mediatype:software',
        'identifier:PSX* AND mediatype:software',
        'identifier:PlayStation* AND mediatype:software',
        'identifier:sony*playstation*',
        'identifier:sony*psx*',
        'identifier:redump*psx*',
        'identifier:Redump*PSX*',
        'identifier:chd*psx*',
        'identifier:PS1*',
        'identifier:ps1*',
        'title:"playstation" AND mediatype:software',
        'title:"psx" AND mediatype:software',
    ]

    all_ids = set()
    for q in queries:
        docs = advanced_search(q, rows=1000)
        for d in docs:
            ident = d.get('identifier', '')
            if ident and ident not in existing_colls:
                all_ids.add(ident)
        print(f"  Query '{q[:40]}': {len(docs)} resultados", flush=True)

    # Filtrar colecoes que parecem ter ROMs PSX
    to_index = []
    for ident in sorted(all_ids):
        # Filtrar colecoes obviamente irrelevantes
        lower = ident.lower()
        if any(skip in lower for skip in ['cover', 'scan', 'manual', 'magazine', 'review',
                                           'soundtrack', 'music', 'video', 'trailer',
                                           'strategy', 'guide', 'cheat', 'save',
                                           'memory', 'bios', 'firmware']):
            continue
        to_index.append(ident)

    print(f"\nColecoes para indexar: {len(to_index)}", flush=True)
    for c in to_index[:30]:
        print(f"  {c}", flush=True)
    if len(to_index) > 30:
        print(f"  ... e mais {len(to_index) - 30}", flush=True)

    # Indexar em paralelo
    all_entries = []
    indexed = 0

    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(index_collection, c): c for c in to_index}
        for f in as_completed(futures):
            coll = futures[f]
            try:
                ident, entries = f.result()
                if entries:
                    all_entries.extend(entries)
                    indexed += 1
                    serials = sum(1 for e in entries if e['serial'])
                    print(f"  [OK] {ident}: {len(entries)} ROMs ({serials} com serial)", flush=True)
            except:
                pass

    print(f"\nIndexadas: {indexed}, Total ROMs: {len(all_entries)}", flush=True)

    # Construir indice por serial
    by_serial = {}
    for entry in all_entries:
        serial = entry.get('serial')
        if serial:
            if serial not in by_serial:
                by_serial[serial] = []
            by_serial[serial].append(entry)

    print(f"Serials no indice extra: {len(by_serial)}", flush=True)

    # Salvar
    with open(EXTRA_INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump({
            'by_serial': by_serial,
            'all_entries': all_entries,
            'total_roms': len(all_entries),
            'total_serials': len(by_serial),
        }, f, ensure_ascii=False, indent=2)

    print(f"Salvo em: {EXTRA_INDEX_PATH}", flush=True)

    # Verificar quantos dos 325 faltantes foram encontrados
    with open(os.path.join(STATE_DIR, 'cross_index_results.json'), 'r', encoding='utf-8') as f:
        cross = json.load(f)
    cross_not_found = set(cross.get('not_found', []))

    found_now = []
    for serial in cross_not_found:
        if serial.upper() in by_serial:
            found_now.append(serial)

    print(f"\nDos 325 faltantes, {len(found_now)} encontrados no indice extra!", flush=True)
    for s in found_now[:20]:
        entries = by_serial[s.upper()]
        print(f"  {s}: {entries[0]['collection']} -> {entries[0]['filename'][:40]}", flush=True)


if __name__ == '__main__':
    main()
