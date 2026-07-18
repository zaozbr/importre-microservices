import requests, re, time, os
from bs4 import BeautifulSoup

# Approach: get everything in one shot, then download with a completely fresh connection
# Close all connections before downloading

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Step 1: Get rom page and download page in one session, extract pluto link
session = requests.Session()
session.headers.update(HEADERS)

r = session.get('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break

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

if not selected:
    print("No USA link!")
    exit(1)

pluto_url, filename = selected
print(f"Target: {filename}")

# Get cookies from session
cookies = dict(session.cookies)

# CRITICAL: Close the session completely
session.close()
print("Session closed. Waiting 30s...")
time.sleep(30)

# Step 2: Download with a completely fresh session
print("Starting fresh download session...")
session2 = requests.Session()
session2.headers.update(HEADERS)
session2.cookies.update(cookies)

dest = r'F:\downloads\psx_faltantes\SLUS-00510_fresh.7z'
if os.path.exists(dest):
    os.remove(dest)

t0 = time.time()
try:
    r3 = session2.get(pluto_url, stream=True, timeout=600)
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
        print(f"Downloaded: {size/1024/1024:.1f} MB in {dt:.1f}s ({size/1024/1024/dt:.1f} MB/s)")
    else:
        print(f"Failed: {r3.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    session2.close()
