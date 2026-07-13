"""Testa archive.org via proxy WARP."""
import requests, json

PROXY = {'http': 'socks5://127.0.0.1:40000', 'https': 'socks5://127.0.0.1:40000'}

serials = ['SLPS-01224', 'SLPM-87140', 'SLES-01375', 'SLPS-00606', 'SLPM-86791']
for s in serials:
    r = requests.get('https://archive.org/advancedsearch.php',
                     params={'q': f'"{s}"', 'fl[]': ['identifier', 'title'], 'rows': '5', 'output': 'json'},
                     timeout=15, proxies=PROXY)
    d = r.json()
    docs = d.get('response', {}).get('docs', [])
    print(f"\n[{s}] {len(docs)} resultados:")
    for doc in docs:
        print(f"  {doc.get('identifier','')}: {doc.get('title','')[:80]}")
