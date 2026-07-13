"""
EMERGENCIA: Expande o smart_index com TODAS as colecoes Redump.orgSonyPlayStation-*
que ainda nao foram indexadas. Isso deve encontrar muitos dos 325 ROMs nao encontrados.

Colecoes Redump.orgSonyPlayStation:
- PAL-A, PAL-B, PAL-C, ... PAL-Z (26 colecoes)
- NTSC-U-A, NTSC-U-B, ... NTSC-U-Z (26 colecoes)
- NTSC-J-A, NTSC-J-B, ... NTSC-J-Z (26 colecoes)

Total: 78 colecoes. Indexar todas em paralelo.
"""
import sys, os, time, json, re, threading
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r'D:\roms\library\roms\_importre_state'
INDEX_PATH = os.path.join(STATE_DIR, 'smart_index.json')
EXPANDED_PATH = os.path.join(STATE_DIR, 'smart_index_expanded.json')

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
    """Indexa uma colecao: retorna lista de {serial, filename, size, collection}."""
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
            # Extrair serial do nome do arquivo
            serial = extract_serial(fname)
            # Tambem procurar no title do item
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
    except Exception as e:
        return identifier, []


def main():
    print("=" * 70, flush=True)
    print("EXPAND INDEX — indexando TODAS as colecoes Redump", flush=True)
    print("=" * 70, flush=True)

    # Carregar indice existente
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        index = json.load(f)

    existing_collections = set()
    for entries in index.get('by_serial', {}).values():
        for e in entries:
            existing_collections.add(e['collection'])
    for entries in index.get('by_name', {}).values():
        for e in entries:
            existing_collections.add(e['collection'])

    print(f"Indice atual: {index.get('total_roms', 0)} ROMs, {len(existing_collections)} colecoes", flush=True)

    # Gerar lista de TODAS as colecoes Redump
    all_collections = []
    for region in ['PAL', 'NTSC-U', 'NTSC-J']:
        for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            all_collections.append(f'Redump.orgSonyPlayStation-{region}-{c}')

    # Filtrar colecoes ja indexadas
    to_index = [c for c in all_collections if c not in existing_collections]
    print(f"Colecoes para indexar: {len(to_index)}", flush=True)

    # Indexar em paralelo (20 threads)
    all_entries = []
    indexed = 0
    failed = []

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
                else:
                    failed.append(ident)
            except Exception as e:
                failed.append(coll)
                print(f"  [ER] {coll}: {e}", flush=True)

    print(f"\nIndexadas: {indexed}, Falhas: {len(failed)}", flush=True)
    print(f"Total novos ROMs: {len(all_entries)}", flush=True)

    # Mesclar com indice existente
    by_serial = index.get('by_serial', {})
    by_name = index.get('by_name', {})

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

    for entry in all_entries:
        serial = entry.get('serial')
        if serial:
            if serial not in by_serial:
                by_serial[serial] = []
            # Evitar duplicatas
            exists = any(e['collection'] == entry['collection'] and e['filename'] == entry['filename']
                        for e in by_serial[serial])
            if not exists:
                by_serial[serial].append(entry)

        # Indexar por nome
        fname = entry.get('filename', '')
        # Remover extensao e caminho
        base = os.path.basename(fname)
        base = re.sub(r'\.(bin|cue|iso|img|zip|7z|rar|chd|ecm|pbp)$', '', base, flags=re.I)
        norm = normalize_name(base)
        if norm and len(norm) > 2:
            if norm not in by_name:
                by_name[norm] = []
            exists = any(e['collection'] == entry['collection'] and e['filename'] == entry['filename']
                        for e in by_name[norm])
            if not exists:
                by_name[norm].append(entry)

    total_roms = sum(len(v) for v in by_serial.values()) + sum(len(v) for v in by_name.values())
    # Evitar dupla contagem
    total_unique = len(set())
    all_files = set()
    for entries in by_serial.values():
        for e in entries:
            all_files.add((e['collection'], e['filename']))
    for entries in by_name.values():
        for e in entries:
            all_files.add((e['collection'], e['filename']))

    expanded = {
        'by_serial': by_serial,
        'by_name': by_name,
        'total_roms': len(all_files),
        'total_serials': len(by_serial),
        'total_names': len(by_name),
        'collections_indexed': list(existing_collections) + [c for c in to_index if c not in failed],
    }

    with open(EXPANDED_PATH, 'w', encoding='utf-8') as f:
        json.dump(expanded, f, ensure_ascii=False, indent=2)

    print(f"\n=== INDICE EXPANDIDO ===", flush=True)
    print(f"Total ROMs: {len(all_files)}", flush=True)
    print(f"Total seriais: {len(by_serial)}", flush=True)
    print(f"Total nomes: {len(by_name)}", flush=True)
    print(f"Salvo em: {EXPANDED_PATH}", flush=True)


if __name__ == '__main__':
    main()
