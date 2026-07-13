import requests, urllib.parse
from bs4 import BeautifulSoup
name = 'Celeste Classic PSX'
ddg_url = f'https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(f"{name} ps1 homebrew download")}'
resp = requests.get(ddg_url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
print('status:', resp.status_code)
print('len:', len(resp.text))
print('first 1000:', resp.text[:1000])
# Procurar qualquer link
soup = BeautifulSoup(resp.text, 'lxml')
for a in soup.find_all('a', href=True):
    print('a href:', a['href'][:100], 'text:', a.get_text(strip=True)[:40])
