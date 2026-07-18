import requests, re, time, os, sys
from bs4 import BeautifulSoup

LOG = r'F:\importre_state\test_download.log'

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

log("=== Starting minimal download test ===")

# Wait for TIME_WAIT connections to clear
log("Waiting 60s for TIME_WAIT to clear...")
time.sleep(60)

session = requests.Session()
session.headers.update(HEADERS)

log("Getting rom page...")
r = session.get('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30)
log(f"  Status: {r.status_code}")

soup = BeautifulSoup(r.text, 'html.parser')
dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break
log(f"  DL link found: {bool(dl_link)}")

log("Getting download page...")
r2 = session.get(dl_link, timeout=30)
log(f"  Status: {r2.status_code}")

soup2 = BeautifulSoup(r2.text, 'html.parser')
body = soup2.find('body') or soup2
links = []
for a in body.find_all('a', href=True):
    if 'pluto.romulation.net' in a['href']:
        links.append((a['href'], a.get_text(strip=True)))
log(f"  Pluto links: {len(links)}")

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
    log(f"Downloading: {filename}")

    dest = r'F:\downloads\psx_faltantes\SLUS-00510_min.7z'
    if os.path.exists(dest):
        os.remove(dest)

    t0 = time.time()
    r3 = session.get(pluto_url, stream=True, timeout=600)
    ct = r3.headers.get('content-type', '?')
    log(f"  Response: {r3.status_code}, type: {ct}")

    if r3.status_code == 200 and 'text/html' not in ct:
        total = 0
        with open(dest, 'wb') as f:
            for chunk in r3.iter_content(chunk_size=256*1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
        dt = time.time() - t0
        size = os.path.getsize(dest)
        log(f"  SUCCESS! {size/1024/1024:.1f} MB in {dt:.1f}s")
    else:
        log(f"  FAILED: {r3.text[:200]}")

    session.close()
else:
    log("No USA link found!")
    session.close()

log("=== Done ===")
