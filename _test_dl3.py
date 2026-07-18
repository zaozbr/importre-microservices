import requests, re, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

session = requests.Session()
session.headers.update(HEADERS)

# Step 1: Visit the game page first to get cookies
print("Step 1: Visit game page vault/6455")
r = session.get('https://vimm.net/vault/6455', timeout=30)
print(f'  Status: {r.status_code}, Cookies: {dict(session.cookies)}')

# Extract mediaId
m = re.search(r'name=["\']mediaId["\']\s+value=["\'](\d+)["\']', r.text, re.I)
media_id = m.group(1) if m else None
print(f'  mediaId: {media_id}')

time.sleep(3)

# Step 2: POST to dl3.vimm.net with various approaches
print("\nStep 2: POST to dl3.vimm.net")

# Approach A: Only mediaId, with Referer
print("\n  Approach A: mediaId only + Referer")
r2 = session.post('https://dl3.vimm.net/', 
    data={'mediaId': media_id},
    headers={'Referer': 'https://vimm.net/vault/6455'},
    stream=True, timeout=60, allow_redirects=True)
print(f'  Status: {r2.status_code}, Content-Type: {r2.headers.get("content-type","?")}')
print(f'  Content-Disposition: {r2.headers.get("content-disposition","?")}')
if r2.status_code != 200 or 'text/html' in r2.headers.get('content-type', ''):
    text = r2.text[:500] if 'text/html' in r2.headers.get('content-type', '') else ''
    print(f'  Body: {text[:300]}')
else:
    print(f'  Content-Length: {r2.headers.get("content-length","?")}')

time.sleep(3)

# Approach B: mediaId + alt=0
print("\n  Approach B: mediaId + alt=0")
r3 = session.post('https://dl3.vimm.net/', 
    data={'mediaId': media_id, 'alt': '0'},
    headers={'Referer': 'https://vimm.net/vault/6455'},
    stream=True, timeout=60, allow_redirects=True)
print(f'  Status: {r3.status_code}, Content-Type: {r3.headers.get("content-type","?")}')

time.sleep(3)

# Approach C: GET with mediaId as query param
print("\n  Approach C: GET with query param")
r4 = session.get(f'https://dl3.vimm.net/?mediaId={media_id}',
    headers={'Referer': 'https://vimm.net/vault/6455'},
    stream=True, timeout=60, allow_redirects=True)
print(f'  Status: {r4.status_code}, Content-Type: {r4.headers.get("content-type","?")}')

time.sleep(3)

# Approach D: POST with Origin header
print("\n  Approach D: POST with Origin + Referer")
r5 = session.post('https://dl3.vimm.net/', 
    data={'mediaId': media_id},
    headers={
        'Referer': 'https://vimm.net/vault/6455',
        'Origin': 'https://vimm.net',
    },
    stream=True, timeout=60, allow_redirects=True)
print(f'  Status: {r5.status_code}, Content-Type: {r5.headers.get("content-type","?")}')
print(f'  Content-Disposition: {r5.headers.get("content-disposition","?")}')
if r5.status_code == 200 and 'text/html' not in r5.headers.get('content-type', ''):
    print(f'  Content-Length: {r5.headers.get("content-length","?")}')
    # Save first 1MB to check
    total = 0
    with open(r'F:\downloads\psx_faltantes\test_download.7z', 'wb') as f:
        for chunk in r5.iter_content(chunk_size=256*1024):
            f.write(chunk)
            total += len(chunk)
            if total > 10*1024*1024:  # Stop at 10MB for test
                break
    print(f'  Downloaded: {total} bytes')
else:
    print(f'  Body: {r5.text[:300]}')
