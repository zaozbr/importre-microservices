"""Testa o deep search com seriais pendentes."""
import sys, json, time
sys.path.insert(0, r'D:\roms\library\roms\psx')
from _deep_search import search_deep, resolve_name, generate_term_variations

# Carregar pendentes
with open(r'D:\roms\library\roms\_importre_state\queue.json', 'r', encoding='utf-8') as f:
    q = json.load(f)
queue = q.get('queue', [])

print(f"=== DEEP SEARCH TEST ===")
print(f"Pendentes: {len(queue)}")

# Testar com os primeiros 10 seriais (pulando NOSERIAL/BREW)
tested = 0
found = 0
for item in queue:
    if tested >= 10:
        break
    serial = item.get('serial', '')
    name = item.get('name', '')
    
    if serial.startswith(('NOSERIAL', 'BREW')):
        continue
    
    tested += 1
    resolved_name = resolve_name(serial) if not name else name
    print(f"\n[{serial}] (name='{resolved_name}')")
    
    variations = generate_term_variations(serial, resolved_name)
    print(f"  Variacoes ({len(variations)}): {variations[:6]}")
    
    t0 = time.time()
    results = search_deep(serial, resolved_name)
    elapsed = time.time() - t0
    
    if results:
        found += 1
        print(f"  ENCONTRADO! {len(results)} resultados em {elapsed:.1f}s:")
        for r in results[:3]:
            url = r['url'][:120]
            src = r['source']
            fname = r.get('file', '')
            print(f"    [{src}] {url}")
            print(f"      file: {fname}")
    else:
        print(f"  Nao encontrado ({elapsed:.1f}s)")

print(f"\n=== RESUMO ===")
print(f"Testados: {tested} | Encontrados: {found} | Taxa: {found/tested*100:.0f}%" if tested > 0 else "Nenhum testado")
