import requests, re, time, os
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("Waiting 5 minutes for all connections to clear...")
time.sleep(300)

print("Starting download attempt...")
session = requests.Session()
session.headers.update(HEADERS)

# Rom page
r = session.get('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break

# Download page
r2 = session.get(dl_link, timeout=30)
soup2 = BeautifulSoup(r2.text, 'html.parser')
body = soup2.find('body') or soup2
links = []
for a in body.find_all('a', href=True):
    if 'pluto.romulation.net' in a['href']:
        links.append((a['href'], a.get_text(strip=True)))

# Pick USA
selected = None
for u, f in links:
    if '(USA)' in f and 'Rev' not in f:
        selected = (u, f)
        break
if not selected:
    for u, f in links:
        if '(USA)' in f:
            selected = (u, f)
            break

if selected:
    pluto_url, filename = selected
    print(f"Downloading: {filename}")

    dest = r'F:\downloads\psx_faltantes\SLUS-00510_5min.7z'
    if os.path.exists(dest):
        os.remove(dest)

    t0 = time.time()
    r3 = session.get(pluto_url, stream=True, timeout=600)
    print(f"Response: {r3.status_code}, type: {r3.headers.get('content-type','?')}")

    if r3.status_code == 200 and 'text/html' not in r3.headers.get('content-type', ''):
        total = 0
        with open(dest, 'wb') as f:
            for chunk in r3.iter_content(chunk_size=256*1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
        dt = time.time() - t0
        size = os.path.getsize(dest)
        print(f"SUCCESS! Downloaded: {size/1024/1024:.1f} MB in {dt:.1f}s ({size/1024/1024/dt:.1f} MB/s)")
    else:
        print(f"FAILED: {r3.text[:200]}")

    session.close()
