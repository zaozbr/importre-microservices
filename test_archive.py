import requests, json
from urllib.parse import quote

serial = 'SLUS-00510'
query = f'"{serial}"'
url = f'https://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&fl[]=title&rows=10&output=json'
r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
print(f'Status: {r.status_code}')
data = r.json()
docs = data.get('response', {}).get('docs', [])
print(f'Results: {len(docs)}')
for d in docs[:5]:
    print(f'  {d.get("identifier")} -> {d.get("title","")[:60]}')

if docs:
    identifier = docs[0]['identifier']
    # Get files
    url2 = f'https://archive.org/metadata/{identifier}'
    r2 = requests.get(url2, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    data2 = r2.json()
    files = data2.get('files', [])
    server = data2.get('server', '')
    print(f'\nItem: {identifier}')
    print(f'Server: {server}')
    print(f'Files: {len(files)}')
    for f in files[:10]:
        name = f.get('name', '')
        fmt = f.get('format', '')
        size = f.get('size', '0')
        if any(name.lower().endswith(ext) for ext in ['.7z', '.zip', '.rar', '.cue', '.bin', '.iso']):
            print(f'  {name} ({fmt}, {size} bytes)')
