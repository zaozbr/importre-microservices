import requests, re, time
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Fresh session
session = requests.Session()
session.headers.update(HEADERS)

# Wait 60s for any lingering connections to expire
print("Waiting 60s for connections to clear...")
time.sleep(60)

# Get rom page
r = session.get('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break

# Get download page
r2 = session.get(dl_link, timeout=30)
soup2 = BeautifulSoup(r2.text, 'html.parser')

# Look for countdown or wait timer in scripts
for script in soup2.find_all('script'):
    stext = script.get_text()
    if any(kw in stext.lower() for kw in ['countdown', 'timer', 'wait', 'delay', 'settimeout', 'setinterval']):
        print("SCRIPT with timer:")
        print(stext[:500])
        print("---")

# Also check for any hidden download buttons or data attributes
body = soup2.find('body')
if body:
    for div in body.find_all(['div', 'span'], attrs={'data-*': True}):
        print(f"Data attr: {div.attrs}")

# Check all scripts for pluto references
for script in soup2.find_all('script'):
    stext = script.get_text()
    if 'pluto' in stext or 'download' in stext.lower():
        print(f"Script (pluto/download): {stext[:300]}")
        print("---")

# Try to get the pluto links and download immediately
links = []
for a in soup2.find_all('a', href=True):
    if 'pluto.romulation.net' in a['href']:
        links.append((a['href'], a.get_text(strip=True)))

if links:
    # Pick USA
    for u, f in links:
        if '(USA)' in f:
            print(f"\nDownloading: {f}")
            import os
            dest = r'F:\downloads\psx_faltantes\SLUS-00510_test.7z'
            if os.path.exists(dest):
                os.remove(dest)
            r3 = session.get(u, stream=True, timeout=600)
            print(f'Response: {r3.status_code}, type: {r3.headers.get("content-type","?")}')
            if r3.status_code == 200 and 'text/html' not in r3.headers.get('content-type', ''):
                total = 0
                t0 = time.time()
                with open(dest, 'wb') as fw:
                    for chunk in r3.iter_content(chunk_size=256*1024):
                        if chunk:
                            fw.write(chunk)
                            total += len(chunk)
                dt = time.time() - t0
                print(f'Downloaded: {total/1024/1024:.1f} MB in {dt:.1f}s')
            else:
                print(f'Failed: {r3.text[:200]}')
            break
