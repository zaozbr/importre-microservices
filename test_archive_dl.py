import requests, os, time

# Try downloading the CHD file from psx_vigil8a
identifier = 'psx_vigil8a'
filename = 'playstationdisc.chd'

# Get server
url = f'https://archive.org/metadata/{identifier}'
r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
data = r.json()
server = data.get('server', '')
print(f'Server: {server}')

# Build download URL
if server:
    dl_url = f'https://{server}/download/{identifier}/{filename}'
else:
    dl_url = f'https://archive.org/download/{identifier}/{filename}'

print(f'Download URL: {dl_url}')

# Try HEAD request first
r_head = requests.head(dl_url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True)
print(f'HEAD status: {r_head.status_code}')
print(f'Content-Type: {r_head.headers.get("content-type", "?")}')
print(f'Content-Length: {r_head.headers.get("content-length", "?")}')

# Try small range download to test
r_range = requests.get(dl_url, timeout=30, headers={'User-Agent': 'Mozilla/5.0', 'Range': 'bytes=0-1023'})
print(f'\nRange request status: {r_range.status_code}')
print(f'Content-Length: {len(r_range.content)}')
if r_range.status_code == 200 or r_range.status_code == 206:
    print('Download accessible!')
    # Check if it's a CHD file (magic bytes)
    magic = r_range.content[:4]
    print(f'Magic bytes: {magic.hex()} ({magic})')
else:
    print(f'Content: {r_range.text[:200]}')
