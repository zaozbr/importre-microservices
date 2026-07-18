import urllib.request, urllib.parse, re, time, os, http.cookiejar
from bs4 import BeautifulSoup

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def fetch_url(url, referer=None, cookies=None):
    """Fetch URL using urllib (no connection pooling)."""
    req = urllib.request.Request(url)
    req.add_header('User-Agent', UA)
    if referer:
        req.add_header('Referer', referer)
    if cookies:
        req.add_header('Cookie', cookies)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        resp_headers = resp.headers
        set_cookies = resp_headers.get_all('Set-Cookie') or []
        return data, resp_headers, set_cookies

# Step 1: Get rom page
print("Step 1: Rom page")
data, headers, set_cookies = fetch_url('https://www.romulation.org/rom/PSX/Vigilante-8')
soup = BeautifulSoup(data, 'html.parser')

# Collect cookies
cookies = {}
for sc in set_cookies:
    parts = sc.split(';')[0].split('=', 1)
    if len(parts) == 2:
        cookies[parts[0].strip()] = parts[1].strip()
print(f"  Cookies: {list(cookies.keys())}")

dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break
print(f"  DL link: {dl_link[:80]}...")

# Step 2: Get download page
print("Step 2: Download page")
cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
data2, headers2, set_cookies2 = fetch_url(dl_link, referer='https://www.romulation.org/rom/PSX/Vigilante-8', cookies=cookie_str)

# Update cookies
for sc in set_cookies2:
    parts = sc.split(';')[0].split('=', 1)
    if len(parts) == 2:
        cookies[parts[0].strip()] = parts[1].strip()
cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())

soup2 = BeautifulSoup(data2, 'html.parser')
body = soup2.find('body') or soup2
links = []
for a in body.find_all('a', href=True):
    if 'pluto.romulation.net' in a['href']:
        links.append((a['href'], a.get_text(strip=True)))
print(f"  Pluto links: {len(links)}")

# Pick USA
selected = None
for u, f in links:
    if '(USA)' in f and 'Rev' not in f:
        selected = (u, f)
        break

if selected:
    pluto_url, filename = selected
    print(f"Step 3: Download {filename}")

    dest = r'F:\downloads\psx_faltantes\SLUS-00510_urllib.7z'
    if os.path.exists(dest):
        os.remove(dest)

    # Download using urllib
    req = urllib.request.Request(pluto_url)
    req.add_header('User-Agent', UA)
    req.add_header('Referer', 'https://www.romulation.org/rom/PSX/Vigilante-8')
    req.add_header('Cookie', cookie_str)

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            ct = resp.headers.get('Content-Type', '?')
            print(f"  Response: {resp.status}, type: {ct}")
            if 'text/html' not in ct:
                total = 0
                with open(dest, 'wb') as f:
                    while True:
                        chunk = resp.read(256*1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        total += len(chunk)
                dt = time.time() - t0
                print(f"  SUCCESS! {total/1024/1024:.1f} MB in {dt:.1f}s")
            else:
                content = resp.read(200)
                print(f"  FAILED: {content.decode('utf-8', errors='ignore')}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP Error: {e.code} - {e.read(200).decode('utf-8', errors='ignore')}")
    except Exception as e:
        print(f"  Error: {e}")
