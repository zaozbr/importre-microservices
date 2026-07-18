import requests, json

# Check psxrip collection
identifier = 'psxrip'
url = f'https://archive.org/metadata/{identifier}'
r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
data = r.json()
files = data.get('files', [])
print(f'psxrip: {len(files)} files')
# Look for Vigilante
vigil_files = [f for f in files if 'vigil' in f.get('name', '').lower()]
print(f'Vigilante files: {len(vigil_files)}')
for f in vigil_files[:5]:
    print(f'  {f.get("name")} | {f.get("format")} | {f.get("size","?")}')

# Check clearancebin item
identifier2 = 'vigilante-8-play-station-ps-1-psone-p-sx'
url2 = f'https://archive.org/metadata/{identifier2}'
r2 = requests.get(url2, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
data2 = r2.json()
files2 = data2.get('files', [])
server2 = data2.get('server', '')
print(f'\n{identifier2}: {len(files2)} files, server={server2}')
for f in files2[:10]:
    name = f.get('name', '')
    fmt = f.get('format', '')
    size = f.get('size', '0')
    print(f'  {name} | {fmt} | {size}')

# Try downloading from clearancebin
if files2 and server2:
    # Find downloadable file
    for f in files2:
        name = f.get('name', '')
        if any(name.lower().endswith(ext) for ext in ['.7z', '.zip', '.rar', '.cue', '.bin', '.iso', '.chd']):
            dl_url = f'https://{server2}/download/{identifier2}/{name}'
            print(f'\nTrying download: {dl_url}')
            r_head = requests.head(dl_url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True)
            print(f'HEAD status: {r_head.status_code}, size: {r_head.headers.get("content-length","?")}')
            break
