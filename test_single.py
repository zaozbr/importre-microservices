import requests, re, os, time, subprocess
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
session = requests.Session()
session.headers.update(HEADERS)

# Test with Vigilante 8 (SLUS-00510, USA)
serial = 'SLUS-00510'
title = 'Vigilante 8'
region = 'USA'

# Step 1: Search
r = session.get(f'https://www.romulation.org/roms/PSX?filter=Vigilante+8', timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
table = soup.select_one('.roms-table')
results = []
if table:
    for tr in table.find_all('tr'):
        a = tr.find('a', href=True)
        if a and '/rom/PSX/' in a['href']:
            href = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
            results.append((href, a.get_text(strip=True)))
print(f'Search results: {len(results)}')
for u, t in results:
    print(f'  {u} -> {t[:50]}')

# Step 2: Get download links from first match
if results:
    rom_url = results[0][0]
    print(f'\nGetting download links from: {rom_url}')
    r2 = session.get(rom_url, timeout=30)
    soup2 = BeautifulSoup(r2.text, 'html.parser')
    dl_link = None
    for a in soup2.find_all('a', href=True):
        if 'newdownload' in a['href']:
            dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
            break
    print(f'Download page: {dl_link[:80]}...' if dl_link else 'No download link')

    if dl_link:
        r3 = session.get(dl_link, timeout=30)
        soup3 = BeautifulSoup(r3.text, 'html.parser')
        body = soup3.find('body') or soup3
        links = []
        for a in body.find_all('a', href=True):
            if 'pluto.romulation.net' in a['href']:
                links.append((a['href'], a.get_text(strip=True)))
        print(f'Pluto links: {len(links)}')
        for u, f in links:
            print(f'  {f}')

        # Select USA link
        selected = None
        for u, f in links:
            if '(USA)' in f:
                selected = (u, f)
                break
        if not selected and links:
            selected = links[0]

        if selected:
            pluto_url, filename = selected
            print(f'\nDownloading: {filename}')
            dest = r'F:\downloads\psx_faltantes\SLUS-00510.7z'
            if os.path.exists(dest):
                os.remove(dest)
            t0 = time.time()
            r4 = session.get(pluto_url, stream=True, timeout=600)
            print(f'Response: {r4.status_code}, content-type: {r4.headers.get("content-type","?")}')
            if r4.status_code == 200 and 'text/html' not in r4.headers.get('content-type', ''):
                total = 0
                with open(dest, 'wb') as f:
                    for chunk in r4.iter_content(chunk_size=256*1024):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
                dt = time.time() - t0
                size = os.path.getsize(dest)
                print(f'Downloaded: {size/1024/1024:.1f} MB in {dt:.1f}s ({size/1024/1024/dt:.1f} MB/s)')
            else:
                print(f'Failed: {r4.text[:200]}')
