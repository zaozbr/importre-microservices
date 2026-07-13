import json
import requests
from bs4 import BeautifulSoup

with open(r'D:/roms/library/roms/_importre_state/coolrom_index.json', 'r') as f:
    idx = json.load(f)

# Pegar alguns jogos para testar
keys = list(idx['cr_data'].keys())[:5]
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

for key in keys:
    entry = idx['cr_data'][key]
    url = f"https://coolrom.com{entry['url']}"
    print(f"\n=== {entry['name']} ===")
    print(f"URL: {url}")
    try:
        r = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
        print(f"Status: {r.status_code}, Final: {r.url}, Len: {len(r.text)}")
        if 'cloudflare' in r.text.lower() or 'cf-browser' in r.text.lower():
            print('CLOUDFLARE DETECTED')
        if 'Access Denied' in r.text or 'blocked' in r.text.lower():
            print('BLOCKED')
        soup = BeautifulSoup(r.text, 'lxml')
        found = False
        for a in soup.find_all('a', href=True):
            if 'dl.coolrom.com' in a['href'] or 'download' in a['href'].lower():
                print(f"Link found: {a['href']}")
                found = True
                break
        if not found:
            print('No download link found')
    except Exception as e:
        print(f"Erro: {e}")
