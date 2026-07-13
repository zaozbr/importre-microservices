import requests
from bs4 import BeautifulSoup
import re

# Buscar link fresco na página de detalhe do coolrom com user-agent móvel
serial = 'SLPM-86975'
name = 'Simple 1500 Series Vol.091 - The Gambler'

ua_mobile = 'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36'
headers = {'User-Agent': ua_mobile}

# Buscar
search_url = f"https://coolrom.com/search?q={name.replace(' ', '+')}&system=psx"
r = requests.get(search_url, timeout=10, headers=headers)
print(f"Search status: {r.status_code}")
soup = BeautifulSoup(r.text, 'lxml')
for a in soup.find_all('a', href=True):
    href = a['href']
    if '/roms/psx/' in href and 'Simple' in a.get_text():
        print(f"Link: {href} text: {a.get_text(strip=True)[:80]}")
        detail_url = 'https://coolrom.com' + href if href.startswith('/') else href
        r2 = requests.get(detail_url, timeout=10, headers=headers)
        print(f"Detail status: {r2.status_code}")
        m = re.search(r"dl\.coolrom\.com/roms/psx/[^\"']+", r2.text)
        if m:
            dl_url = 'https://' + m.group(0)
            print(f"DL URL: {dl_url}")
            r3 = requests.get(dl_url, stream=True, timeout=10, headers=headers)
            print(f"Download status: {r3.status_code}, headers: {r3.headers.get('content-length')}")
            if r3.status_code == 200:
                downloaded = 0
                for chunk in r3.iter_content(chunk_size=1024*1024):
                    if chunk:
                        downloaded += len(chunk)
                        if downloaded > 5 * 1024 * 1024:
                            break
                print(f"Downloaded {downloaded/1024/1024:.1f} MB")
        break
