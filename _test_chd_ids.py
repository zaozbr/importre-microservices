import requests, json

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

# Identifiers encontrados pelo deep_archive
ids = ['psx_blsbball', 'psx_tjstomok', 'psx_momomats', 'jetracer-eu']

for ident in ids:
    url = f'http://archive.org/metadata/{ident}'
    r = s.get(url, timeout=15)
    print(f'\n=== {ident} ===')
    print(f'Metadata: {r.status_code}')
    if r.status_code == 200:
        data = r.json()
        files = data.get('files', [])
        for f in files:
            fname = f.get('name', '')
            size = f.get('size', '0')
            fmt = f.get('format', '?')
            if any(fname.lower().endswith(ext) for ext in ('.zip', '.7z', '.chd', '.bin', '.iso')):
                # Testar download
                from urllib.parse import quote
                dl_url = f'http://archive.org/download/{ident}/{quote(fname, safe="/")}'
                r2 = s.get(dl_url, timeout=10, stream=True)
                print(f'  {fname} ({size} bytes, {fmt}) -> HTTP {r2.status_code}')
                r2.close()
