"""Testa buscas no archive.org via Tor SOCKS5 proxy."""
import requests, json, time

PROXY = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}

serials = ['SLPS-01224', 'SLPM-87140', 'SLES-01375', 'SLPS-00606', 'SLPM-86791',
           'SLPS-01190', 'SLPM-86880', 'SLPS-01269', 'SLPM-86819', 'SLES-02693']

print("=== BUSCA NO ARCHIVE.ORG VIA TOR ===\n")
found = 0
for s in serials:
    t0 = time.time()
    try:
        r = requests.get('https://archive.org/advancedsearch.php',
                        params={'q': f'"{s}"', 'fl[]': ['identifier', 'title'], 'rows': '5', 'output': 'json'},
                        timeout=30, proxies=PROXY)
        elapsed = time.time() - t0
        d = r.json()
        docs = d.get('response', {}).get('docs', [])
        if docs:
            found += 1
            print(f"[{s}] {len(docs)} resultados em {elapsed:.1f}s:")
            for doc in docs:
                print(f"  {doc.get('identifier','')}: {doc.get('title','')[:80]}")
        else:
            print(f"[{s}] 0 resultados em {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[{s}] ERRO em {elapsed:.1f}s: {str(e)[:80]}")

print(f"\n=== RESUMO: {found}/{len(serials)} encontrados ===")
