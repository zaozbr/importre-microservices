"""
Descobre TODAS as colecoes Redump.orgSonyPlayStation-* que existem no archive.org.
Usa o advancedsearch para listar itens com collection:redump ou que comecam com Redump.
"""
import sys, os, json, re
from urllib.parse import quote

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r'D:\roms\library\roms\_importre_state'

COOKIES = {
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
}

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
s.cookies.update(COOKIES)


def search_collections(query, rows=1000):
    url = f"http://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&rows={rows}&page=1&output=json"
    try:
        r = s.get(url, timeout=30)
        if r.status_code == 200:
            return r.json().get('response', {}).get('docs', [])
    except:
        pass
    return []


def main():
    print("Buscando todas as colecoes Redump.orgSonyPlayStation-*...", flush=True)

    # Buscar por prefixo
    all_ids = set()

    # Query 1: identifier prefix
    docs = search_collections('identifier:Redump.orgSonyPlayStation*', rows=1000)
    for d in docs:
        all_ids.add(d['identifier'])
    print(f"  identifier prefix: {len(docs)} resultados", flush=True)

    # Query 2: collection search
    docs = search_collections('collection:Redump.orgSonyPlayStation*', rows=1000)
    for d in docs:
        all_ids.add(d['identifier'])
    print(f"  collection prefix: {len(docs)} resultados", flush=True)

    # Query 3: title search
    docs = search_collections('title:"Redump.org Sony PlayStation"', rows=1000)
    for d in docs:
        all_ids.add(d['identifier'])
    print(f"  title search: {len(docs)} resultados", flush=True)

    # Filtrar apenas os que comecam com Redump.orgSonyPlayStation
    redump_colls = sorted([i for i in all_ids if i.startswith('Redump.orgSonyPlayStation')])
    print(f"\nTotal colecoes Redump.orgSonyPlayStation-*: {len(redump_colls)}", flush=True)

    # Agrupar por regiao
    regions = {}
    for c in redump_colls:
        # Redump.orgSonyPlayStation-PAL-A
        parts = c.split('-')
        if len(parts) >= 3:
            region = parts[2]
            if region not in regions:
                regions[region] = []
            regions[region].append(c)

    for region, colls in sorted(regions.items()):
        print(f"  {region}: {len(colls)} colecoes", flush=True)
        for c in sorted(colls):
            print(f"    {c}", flush=True)

    # Salvar lista
    with open(os.path.join(STATE_DIR, 'all_redump_collections.json'), 'w') as f:
        json.dump(redump_colls, f, indent=2)
    print(f"\nSalvo em all_redump_collections.json", flush=True)

    # Verificar quais ja estao no indice
    with open(os.path.join(STATE_DIR, 'smart_index.json'), 'r', encoding='utf-8') as f:
        index = json.load(f)

    existing = set()
    for entries in index.get('by_serial', {}).values():
        for e in entries:
            existing.add(e['collection'])
    for entries in index.get('by_name', {}).values():
        for e in entries:
            existing.add(e['collection'])

    missing_colls = [c for c in redump_colls if c not in existing]
    print(f"\nColecoes NAO indexadas: {len(missing_colls)}", flush=True)
    for c in missing_colls:
        print(f"  {c}", flush=True)


if __name__ == '__main__':
    main()
