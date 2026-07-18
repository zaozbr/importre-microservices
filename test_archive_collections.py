import requests, json
from urllib.parse import quote

# Search for Vigilante 8 in different collections
serial = 'SLUS-00510'
title = 'Vigilante 8'

# Try different search queries
queries = [
    f'"{serial}" AND NOT collection:psxgames',
    f'Vigilante 8 psx',
    f'Vigilante 8 playstation iso',
    f'Vigilante 8 redump',
]

for q in queries:
    url = f'https://archive.org/advancedsearch.php?q={quote(q)}&fl[]=identifier&fl[]=title&fl[]=collection&rows=10&output=json'
    try:
        r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            data = r.json()
            docs = data.get('response', {}).get('docs', [])
            print(f'Query "{q}": {len(docs)} results')
            for d in docs[:5]:
                print(f'  {d.get("identifier")} | {d.get("collection","")} | {d.get("title","")[:50]}')
    except Exception as e:
        print(f'Error: {e}')
    print()
