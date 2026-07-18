import requests, re
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
session = requests.Session()
session.headers.update(HEADERS)

# Get rom page
r = session.get('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break

# Get download page and examine full content
r2 = session.get(dl_link, timeout=30)
print('=== DOWNLOAD PAGE CONTENT ===')
print(r2.text[:3000])
print('=== COOKIES ===')
for c in session.cookies:
    print(f'{c.name}={c.value[:50]}... domain={c.domain}')
