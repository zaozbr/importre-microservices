import requests, json

# Verificar formato de arquivos em algumas collections
collections = [
    "Redump.orgSonyPlayStation-NTSC-U-S",
    "Redump.orgSonyPlayStation-NTSC-U-B",
    "redump_psx",
    "CuratedPSXRedumpCHDs",
]

for coll in collections:
    print(f"\n=== {coll} ===")
    r = requests.get(f'http://archive.org/metadata/{coll}', timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
    print(f'Status: {r.status_code}')
    if r.status_code == 200:
        data = r.json()
        files = data.get('files', [])
        print(f'Total arquivos: {len(files)}')
        for f in files[:15]:
            name = f.get('name', '?')
            size = f.get('size', '?')
            fmt = f.get('format', '?')
            print(f'  {name} | {size} | {fmt}')
    else:
        print(f'Erro: {r.status_code}')
