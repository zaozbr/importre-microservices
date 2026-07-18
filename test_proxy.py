import requests, re, time, os
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Try with a free proxy
# First, let's try without any proxy but with no cookies
print("Test 1: No cookies at all")
session = requests.Session()
session.headers.update(HEADERS)
session.cookies.clear()

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

selected = None
for u, f in links:
    if '(USA)' in f and 'Rev' not in f:
        selected = (u, f)
        break

if selected:
    pluto_url, filename = selected
    print(f"  Target: {filename}")

    # Try downloading with NO cookies
    dest = r'F:\downloads\psx_faltantes\SLUS-00510_nocookies.7z'
    if os.path.exists(dest):
        os.remove(dest)

    # Use a completely fresh request with no session
    r3 = requests.get(pluto_url, stream=True, timeout=600,
                       headers={**HEADERS,
                                'Referer': 'https://www.romulation.org/rom/PSX/Vigilante-8'})
    print(f"  Response: {r3.status_code}, type: {r3.headers.get('content-type','?')}")
    if r3.status_code == 200 and 'text/html' not in r3.headers.get('content-type', ''):
        total = 0
        with open(dest, 'wb') as f:
            for chunk in r3.iter_content(chunk_size=256*1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
        print(f"  SUCCESS! {total/1024/1024:.1f} MB")
    else:
        print(f"  Failed: {r3.text[:200]}")

# Test 2: Try with a free HTTP proxy
print("\nTest 2: With free proxy")
# Try some common free proxies
proxies_to_try = [
    'http://47.88.31.78:8080',
    'http://103.155.54.46:80',
    'http://167.172.180.46:39591',
]

for proxy_url in proxies_to_try:
    print(f"  Trying proxy: {proxy_url}")
    try:
        r = requests.get('https://pluto.romulation.net/', timeout=10,
                        proxies={'https': proxy_url, 'http': proxy_url},
                        headers=HEADERS)
        print(f"    Status: {r.status_code}, Content: {r.text[:100]}")
        if r.status_code == 200 and 'Yaar' in r.text:
            print(f"    Proxy works! Using it for download...")

            # Get pluto link through proxy
            session_proxy = requests.Session()
            session_proxy.headers.update(HEADERS)
            session_proxy.proxies = {'https': proxy_url, 'http': proxy_url}

            r_rom = session_proxy.get('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30)
            soup = BeautifulSoup(r_rom.text, 'html.parser')
            dl_link = None
            for a in soup.find_all('a', href=True):
                if 'newdownload' in a['href']:
                    dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
                    break

            if dl_link:
                r_dl = session_proxy.get(dl_link, timeout=30)
                soup2 = BeautifulSoup(r_dl.text, 'html.parser')
                body = soup2.find('body') or soup2
                links = []
                for a in body.find_all('a', href=True):
                    if 'pluto.romulation.net' in a['href']:
                        links.append((a['href'], a.get_text(strip=True)))

                selected = None
                for u, f in links:
                    if '(USA)' in f and 'Rev' not in f:
                        selected = (u, f)
                        break

                if selected:
                    pluto_url, filename = selected
                    print(f"    Downloading via proxy: {filename}")
                    dest = r'F:\downloads\psx_faltantes\SLUS-00510_proxy.7z'
                    if os.path.exists(dest):
                        os.remove(dest)
                    r3 = session_proxy.get(pluto_url, stream=True, timeout=600)
                    print(f"    Response: {r3.status_code}, type: {r3.headers.get('content-type','?')}")
                    if r3.status_code == 200 and 'text/html' not in r3.headers.get('content-type', ''):
                        total = 0
                        with open(dest, 'wb') as f:
                            for chunk in r3.iter_content(chunk_size=256*1024):
                                if chunk:
                                    f.write(chunk)
                                    total += len(chunk)
                        print(f"    SUCCESS! {total/1024/1024:.1f} MB")
                        break
                    else:
                        print(f"    Failed: {r3.text[:200]}")
    except Exception as e:
        print(f"    Error: {e}")
        continue
