"""Testa buscas no archive.org via Tor usando NOME RESOLVIDO (nao so serial)."""
import requests, json, time, sys, os
sys.path.insert(0, r'D:\roms\library\roms\psx')
from _deep_search import resolve_name, generate_term_variations

PROXY = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}

# Pendentes da fila
with open(r'D:\roms\library\roms\_importre_state\queue.json', 'r', encoding='utf-8') as f:
    q = json.load(f)
queue = q.get('queue', [])

print(f"=== BUSCA NO ARCHIVE.ORG VIA TOR (POR NOME) ===")
print(f"Pendentes: {len(queue)}\n")

found = 0
for item in queue:
    serial = item.get('serial', '')
    name = item.get('name', '') or resolve_name(serial)

    if serial.startswith(('NOSERIAL', 'BREW')):
        continue

    # Gerar variacoes
    variations = generate_term_variations(serial, name)

    # Tentar busca por NOME no archive.org (nao so serial)
    best_result = None
    for v in variations[:5]:
        try:
            r = requests.get('https://archive.org/advancedsearch.php',
                            params={'q': v, 'fl[]': ['identifier', 'title'], 'rows': '3', 'output': 'json'},
                            timeout=20, proxies=PROXY)
            d = r.json()
            docs = d.get('response', {}).get('docs', [])
            if docs:
                best_result = (v, docs)
                break
        except:
            pass

    if best_result:
        v, docs = best_result
        found += 1
        print(f"[{serial}] '{name[:40]}' -> query='{v[:40]}'")
        for doc in docs:
            print(f"  {doc.get('identifier','')}: {doc.get('title','')[:80]}")
    else:
        print(f"[{serial}] '{name[:40]}' -> NAO ENCONTRADO")

print(f"\n=== RESUMO: {found} encontrados ===")
