import requests, re, time, os, subprocess
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("Waiting 120s for any lingering connections to clear...")
time.sleep(120)

session = requests.Session()
session.headers.update(HEADERS)

# Fresh rom page
r = session.get('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break

# Fresh download page
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

    # Export cookies for curl
    cookie_str = "; ".join(f"{c.name}={c.value}" for c in session.cookies)
    print(f"Cookies: {cookie_str[:80]}...")

    dest = r'F:\downloads\psx_faltantes\SLUS-00510_curl.7z'
    if os.path.exists(dest):
        os.remove(dest)

    # Use curl with cookies
    cmd = ['curl', '-L', '-o', dest,
           '--connect-timeout', '30', '--max-time', '600',
           '-H', f'User-Agent: {HEADERS["User-Agent"]}',
           '-H', f'Referer: https://www.romulation.org/rom/PSX/Vigilante-8',
           '-H', f'Cookie: {cookie_str}',
           '-s', '--show-error', '-w', '\\nHTTP_CODE:%{http_code} SIZE:%{size_download} TIME:%{time_total}',
           pluto_url]

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=620)
    dt = time.time() - t0
    print(f"curl output: {result.stdout}")
    print(f"curl stderr: {result.stderr[:200]}")
    print(f"rc={result.returncode}, time={dt:.1f}s")

    if os.path.exists(dest):
        size = os.path.getsize(dest)
        print(f"File size: {size} bytes ({size/1024/1024:.1f} MB)")
        if size < 1024:
            with open(dest, 'r', errors='ignore') as f:
                print(f"Content: {f.read()[:300]}")
        else:
            print("SUCCESS!")
    else:
        print("File not created")
