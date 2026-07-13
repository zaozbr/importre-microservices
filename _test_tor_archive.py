"""Testa acesso ao archive.org via Tor (torpy)."""
import time, json

print("=== TESTE TOR -> ARCHIVE.ORG ===\n")

# Metodo 1: torpy HTTP adapter
print("1. Torpy HTTP adapter")
try:
    from torpy.http.requests import TorRequests
    import requests

    with TorRequests() as tor_requests:
        session = tor_requests.get_session()

        t0 = time.time()
        r = session.get('https://archive.org/advancedsearch.php',
                        params={'q': 'test', 'output': 'json'},
                        timeout=30)
        elapsed = time.time() - t0
        print(f"   Status: {r.status_code} em {elapsed:.1f}s, {len(r.text)} bytes")

        # Testar busca real
        print("\n2. Busca real no archive.org via Tor")
        t0 = time.time()
        r = session.get('https://archive.org/advancedsearch.php',
                        params={'q': '"SLPS-01224"', 'fl[]': ['identifier', 'title'], 'rows': '5', 'output': 'json'},
                        timeout=30)
        elapsed = time.time() - t0
        d = r.json()
        docs = d.get('response', {}).get('docs', [])
        print(f"   Status: {r.status_code} em {elapsed:.1f}s, {len(docs)} resultados")
        for doc in docs:
            print(f"     {doc.get('identifier','')}: {doc.get('title','')[:80]}")

        # Testar mais seriais
        print("\n3. Busca em lote via Tor")
        serials = ['SLPM-87140', 'SLES-01375', 'SLPS-00606', 'SLPM-86791', 'SLPS-01190']
        for s in serials:
            t0 = time.time()
            r = session.get('https://archive.org/advancedsearch.php',
                            params={'q': f'"{s}"', 'fl[]': ['identifier', 'title'], 'rows': '3', 'output': 'json'},
                            timeout=30)
            elapsed = time.time() - t0
            d = r.json()
            docs = d.get('response', {}).get('docs', [])
            print(f"   [{s}] {len(docs)} resultados em {elapsed:.1f}s")
            for doc in docs:
                print(f"     {doc.get('identifier','')}: {doc.get('title','')[:80]}")

except Exception as e:
    import traceback
    print(f"   ERRO: {e}")
    traceback.print_exc()

print("\n=== FIM ===")
