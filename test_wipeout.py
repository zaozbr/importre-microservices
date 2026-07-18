import requests, re, time, os
from bs4 import BeautifulSoup

LOG = r'F:\importre_state\test_wipeout.log'

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
session = requests.Session()
session.headers.update(HEADERS)

log("=== Testing with Wipeout XL ===")

# Search
r = session.get('https://www.romulation.org/roms/PSX?filter=Wipeout', timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
table = soup.select_one('.roms-table')
roms = []
if table:
    for tr in table.find_all('tr'):
        a = tr.find('a', href=True)
        if a and '/rom/PSX/' in a['href']:
            href = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
            roms.append((href, a.get_text(strip=True)))

log(f"Found {len(roms)} roms")
for u, t in roms:
    log(f"  {u} -> {t[:50]}")

# Use Wipeout XL
if roms:
    rom_url = roms[0][0]
    log(f"Using: {rom_url}")

    # Get download page
    r2 = session.get(rom_url, timeout=30)
    soup2 = BeautifulSoup(r2.text, 'html.parser')
    dl_link = None
    for a in soup2.find_all('a', href=True):
        if 'newdownload' in a['href']:
            dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
            break

    if dl_link:
        log(f"DL page: {dl_link[:80]}...")
        r3 = session.get(dl_link, timeout=30)
        soup3 = BeautifulSoup(r3.text, 'html.parser')
        body = soup3.find('body') or soup3
        links = []
        for a in body.find_all('a', href=True):
            if 'pluto.romulation.net' in a['href']:
                links.append((a['href'], a.get_text(strip=True)))

        log(f"Pluto links: {len(links)}")
        for u, f in links:
            log(f"  {f}")

        # Pick Europe (for SLES-00327)
        selected = None
        for u, f in links:
            if 'Europe' in f or '(E)' in f:
                selected = (u, f)
                break
        if not selected and links:
            selected = links[0]

        if selected:
            pluto_url, filename = selected
            log(f"Downloading: {filename}")

            dest = r'F:\downloads\psx_faltantes\SLES-00327_test.7z'
            if os.path.exists(dest):
                os.remove(dest)

            r4 = session.get(pluto_url, stream=True, timeout=600)
            ct = r4.headers.get('content-type', '?')
            log(f"Response: {r4.status_code}, type: {ct}")

            if r4.status_code == 200 and 'text/html' not in ct:
                total = 0
                t0 = time.time()
                with open(dest, 'wb') as f:
                    for chunk in r4.iter_content(chunk_size=256*1024):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
                dt = time.time() - t0
                log(f"SUCCESS! {total/1024/1024:.1f} MB in {dt:.1f}s")
            else:
                log(f"FAILED: {r4.text[:200]}")

session.close()
log("=== Done ===")
