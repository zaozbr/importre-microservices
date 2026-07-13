import json, requests, re, time
from pathlib import Path
from bs4 import BeautifulSoup

STATE_DIR = Path('D:/roms/library/roms/_importre_state')
with open(STATE_DIR / 'sites.json', 'r') as f:
    sites = json.load(f)

# Testar um item EU e um US
items = [
    ('SLES-02902', 'Batman Beyond: Return of the Joker', 'EU'),
    ('SLUS-00426', 'MDK', 'US'),
]

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

for serial, name, region in items:
    print(f"\n=== {serial} {name} ({region}) ===")
    for site_key, cfg in sites.items():
        if not cfg.get('enabled') or site_key in ['archive_org', 'archive_org_jp', 'coolrom', 'vimm']:
            continue
        url_template = cfg.get('search_url', '')
        if not url_template:
            continue
        try:
            url = url_template.format(query=name.replace(' ', '+'))
        except:
            continue
        print(f"  {site_key}: {url[:80]}", end=' ')
        try:
            r = requests.get(url, timeout=10, headers=headers)
            print(f"status={r.status_code} len={len(r.text)}")
            # procurar serial na página
            if serial.lower().replace('-', '') in r.text.lower().replace('-', ''):
                print(f"    -> SERIAL FOUND")
        except Exception as e:
            print(f"ERRO {str(e)[:60]}")
