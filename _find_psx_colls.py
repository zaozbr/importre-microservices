"""
Busca colecoes PSX no archive.org usando queries de texto (sem wildcard).
"""
import sys, os, json, re
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r'D:\roms\library\roms\_importre_state'

COOKIES = {
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
}

ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
s.cookies.update(COOKIES)


def search(query, rows=1000):
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
            entries.append({
                'serial': serial,
                'filename': fname,
                'size': f.get('size', '0'),
                'collection': identifier,
            })
        return identifier, entries
    except:
        return identifier, []


# Carregar colecoes ja conhecidas
with open(os.path.join(STATE_DIR, 'smart_index.json'), 'r', encoding='utf-8') as f:
    index = json.load(f)
existing_colls = set()
for entries in index.get('by_serial', {}).values():
    for e in entries:
        existing_colls.add(e['collection'])
for entries in index.get('by_name', {}).values():
    for e in entries:
        existing_colls.add(e['collection'])
with open(os.path.join(STATE_DIR, 'all_redump_collections.json'), 'r') as f:
    existing_colls.update(json.load(f))

print(f"Colecoes ja conhecidas: {len(existing_colls)}", flush=True)

# Queries de texto (sem wildcard)
queries = [
    'psx rom',
    'psx iso',
    'psx redump',
    'psx chd',
    'playstation rom',
    'playstation iso',
    'playstation redump',
    'playstation chd',
    'ps1 rom',
    'ps1 iso',
    'ps1 redump',
    'sony playstation',
    'playstation collection',
    'psx collection',
    'psx set',
    'playstation set',
    'psx archive',
    'playstation archive',
    'psx library',
    'playstation library',
    'redump psx',
    'redump playstation',
    'redump sony',
    'psx games',
    'playstation games',
    'ps1 games',
]

all_ids = set()
for q in queries:
    docs = search(q, rows=500)
    for d in docs:
        ident = d.get('identifier', '')
        if ident and ident not in existing_colls:
            all_ids.add(ident)
    print(f"  '{q}': {len(docs)} resultados, {len(all_ids)} novos", flush=True)

# Filtrar colecoes irrelevantes
to_index = []
for ident in sorted(all_ids):
    lower = ident.lower()
    if any(skip in lower for skip in ['cover', 'scan', 'manual', 'magazine', 'review',
                                       'soundtrack', 'music', 'video', 'trailer',
                                       'strategy', 'guide', 'cheat', 'save',
                                       'memory', 'bios', 'firmware', 'book',
                                       'documentary', 'history', 'document',
                                       'artbook', 'concept', 'gallery']):
        continue
    to_index.append(ident)

print(f"\nColecoes para indexar: {len(to_index)}", flush=True)
for c in to_index[:50]:
    print(f"  {c}", flush=True)

# Indexar em paralelo
all_entries = []
with ThreadPoolExecutor(max_workers=20) as ex:
    futures = {ex.submit(index_collection, c): c for c in to_index}
    for f in as_completed(futures):
        coll = futures[f]
        try:
            ident, entries = f.result()
            if entries:
                all_entries.extend(entries)
                serials = sum(1 for e in entries if e['serial'])
                print(f"  [OK] {ident}: {len(entries)} ROMs ({serials} com serial)", flush=True)
        except:
            pass

# Construir indice por serial
by_serial = {}
for entry in all_entries:
    serial = entry.get('serial')
    if serial:
        if serial not in by_serial:
            by_serial[serial] = []
        by_serial[serial].append(entry)

print(f"\nTotal ROMs: {len(all_entries)}, Serials: {len(by_serial)}", flush=True)

# Salvar
EXTRA_INDEX_PATH = os.path.join(STATE_DIR, 'extra_index.json')
with open(EXTRA_INDEX_PATH, 'w', encoding='utf-8') as f:
    json.dump({
        'by_serial': by_serial,
        'all_entries': all_entries,
        'total_roms': len(all_entries),
        'total_serials': len(by_serial),
    }, f, ensure_ascii=False, indent=2)

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
