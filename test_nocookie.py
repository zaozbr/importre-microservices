import requests, re, time, os
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Completely fresh session, no cookies carried over
session = requests.Session()
session.headers.update(HEADERS)
# Disable connection pooling to force new connections
session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1))

print("Step 1: Rom page")
r = session.get('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30)
print(f"  Status: {r.status_code}, Cookies: {len(session.cookies)}")

soup = BeautifulSoup(r.text, 'html.parser')
dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break

print(f"Step 2: Download page")
r2 = session.get(dl_link, timeout=30)
print(f"  Status: {r2.status_code}")

soup2 = BeautifulSoup(r2.text, 'html.parser')
body = soup2.find('body') or soup2
links = []
for a in body.find_all('a', href=True):
    if 'pluto.romulation.net' in a['href']:
        links.append((a['href'], a.get_text(strip=True)))

# Pick USA (non-Rev)
selected = None
for u, f in links:
    if '(USA)' in f and 'Rev' not in f:
        selected = (u, f)
        break

if selected:
    pluto_url, filename = selected
    print(f"Step 3: Download {filename}")
    print(f"  Pluto URL: {pluto_url[:80]}...")

    # Get cookies as string
    cookie_str = "; ".join(f"{c.name}={c.value}" for c in session.cookies)

    # Close the session to release connections
    session.close()
    print("  Session closed, waiting 5s...")
    time.sleep(5)

    # Download with a brand new connection, passing cookies manually
    dest = r'F:\downloads\psx_faltantes\SLUS-00510_nocookie.7z'
    if os.path.exists(dest):
        os.remove(dest)

    # Use requests with explicit cookies but no session
    r3 = requests.get(pluto_url, stream=True, timeout=600,
                       headers={**HEADERS,
                                'Cookie': cookie_str,
                                'Referer': 'https://www.romulation.org/rom/PSX/Vigilante-8'})
    print(f"  Response: {r3.status_code}, type: {r3.headers.get('content-type','?')}")

    if r3.status_code == 200 and 'text/html' not in r3.headers.get('content-type', ''):
        total = 0
        t0 = time.time()
        with open(dest, 'wb') as f:
            for chunk in r3.iter_content(chunk_size=256*1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
        dt = time.time() - t0
        print(f"  Downloaded: {total/1024/1024:.1f} MB in {dt:.1f}s")
    else:
        print(f"  Failed: {r3.text[:200]}")
