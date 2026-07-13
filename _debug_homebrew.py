import sys
sys.path.insert(0, r'D:\roms\library\roms\psx')
from importre import SiteNavigator
from playwright.sync_api import sync_playwright
import requests
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import urllib.parse

name = 'Celeste Classic PSX'
req_headers = {'User-Agent': 'Mozilla/5.0'}
search_terms = [
    f'"{name}" ps1 homebrew download',
    f'"{name}" psx homebrew download',
]
for ddg_query in search_terms:
    ddg_url = f'https://html.duckduckgo.com/html/?q={quote_plus(ddg_query)}'
    resp = requests.get(ddg_url, timeout=15, headers=req_headers)
    print('ddg status:', resp.status_code)
    soup = BeautifulSoup(resp.text, 'lxml')
    results = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        real_url = None
        if 'uddg=' in href:
            real_url = urllib.parse.unquote(href.split('uddg=')[1].split('&')[0])
        elif href.startswith('http') and 'duckduckgo' not in href:
            real_url = href
        if real_url and text and len(text) > 3 and 'duckduckgo' not in real_url.lower():
            results.append((real_url, text))
    print('results:', len(results))
    for u, t in results[:5]:
        print(' ', u[:80], '|', t[:40])
