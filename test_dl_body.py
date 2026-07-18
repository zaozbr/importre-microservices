import requests, re
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
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
# Find the body content
soup2 = BeautifulSoup(r2.text, 'html.parser')
body = soup2.find('body')
if body:
    # Remove script and style tags
    for s in body.find_all(['script', 'style']):
        s.decompose()
    text = body.get_text(separator='\n', strip=True)
    print('=== BODY TEXT ===')
    print(text[:2000])
    print('\n=== LINKS ===')
    for a in body.find_all('a', href=True):
        print(f'  {a["href"][:120]} -> {a.get_text(strip=True)[:50]}')
    print('\n=== SCRIPTS with pluto ===')
    for script in soup2.find_all('script'):
        stext = script.get_text()
        if 'pluto' in stext or 'download' in stext.lower() or 'countdown' in stext.lower():
            print(stext[:500])
            print('---')
