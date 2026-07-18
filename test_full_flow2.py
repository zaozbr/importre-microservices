import requests, re, os, time
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Use a session to maintain cookies
session = requests.Session()
session.headers.update(HEADERS)

# Step 1: Get rom page
r = session.get('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30)
print(f'Rom page: {r.status_code}')
soup = BeautifulSoup(r.text, 'html.parser')
dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break
print(f'DL link: {dl_link[:80]}...')

# Step 2: Get pluto link
r2 = session.get(dl_link, timeout=30)
print(f'DL page: {r2.status_code}')
links = re.findall(r'https://pluto\.romulation\.net/files/guest/[^\s"<>]+', r2.text)
print(f'Pluto links: {len(links)}')

# Step 3: Download with session (same cookies)
pluto_url = links[0]
dest = r'F:\downloads\psx_faltantes\SLUS-00510.rar'
if os.path.exists(dest):
    os.remove(dest)

t0 = time.time()
r3 = session.get(pluto_url, stream=True, timeout=300)
print(f'Download response: {r3.status_code}, content-type: {r3.headers.get("content-type","?")}, content-length: {r3.headers.get("content-length","?")}')

if r3.status_code == 200:
    with open(dest, 'wb') as f:
        for chunk in r3.iter_content(chunk_size=1024*256):
            f.write(chunk)
    dt = time.time() - t0
    size = os.path.getsize(dest)
    print(f'Downloaded: {size} bytes ({size/1024/1024:.1f} MB) in {dt:.1f}s')
    if size < 1024:
        with open(dest, 'r', errors='ignore') as f:
            print('Content:', f.read()[:300])
    else:
        print('SUCCESS!')
else:
    print(f'Failed: {r3.text[:200]}')
