"""
Indexa TODAS as colecoes que o indice JP conhece.
O indice JP tem 1693 entradas de colecoes que podem ter mais ROMs.
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
JP_EXTRA_INDEX = os.path.join(STATE_DIR, 'jp_extra_index.json')

COOKIES = {
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
}

ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
s.cookies.update(COOKIES)


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


# Carregar indice JP
with open(os.path.join(STATE_DIR, 'archive_jp_index.json')) as f:
    jp = json.load(f)

# Extrair todas as colecoes do indice JP
jp_colls = set()
for serial, info in jp.items():
    if isinstance(info, dict):
        coll = info.get('collection', '')
        if coll:
            jp_colls.add(coll)

print(f"Colecoes no indice JP: {len(jp_colls)}", flush=True)
for c in sorted(jp_colls):
    print(f"  {c}", flush=True)

# Carregar colecoes ja indexadas
with open(os.path.join(STATE_DIR, 'smart_index.json'), 'r', encoding='utf-8') as f:
    index = json.load(f)
existing_colls = set()
for entries in index.get('by_serial', {}).values():
    for e in entries:
        existing_colls.add(e['collection'])
for entries in index.get('by_name', {}).values():
    for e in entries:
        existing_colls.add(e['collection'])

# Filtrar colecoes nao indexadas
to_index = [c for c in jp_colls if c not in existing_colls]
print(f"\nColecoes para indexar: {len(to_index)}", flush=True)

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
with open(JP_EXTRA_INDEX, 'w', encoding='utf-8') as f:
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

print(f"\nDos 325 faltantes, {len(found_now)} encontrados!", flush=True)
for s in found_now[:30]:
    entries = by_serial[s.upper()]
    e = entries[0]
    print(f"  {s}: {e['collection']} -> {e['filename'][:50]}", flush=True)
