import requests, json

identifier = 'psx_vigil8a'
url = f'https://archive.org/metadata/{identifier}'
r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
data = r.json()
files = data.get('files', [])
server = data.get('server', '')
print(f'Item: {identifier}')
print(f'Server: {server}')
print(f'Files: {len(files)}')
for f in files:
    name = f.get('name', '')
    fmt = f.get('format', '')
    size = f.get('size', '0')
    print(f'  {name} | {fmt} | {size}')
