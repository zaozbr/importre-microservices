"""Analisa formato dos itens pendentes e completados."""
import json

QUEUE = r'D:\roms\library\roms\_importre_state\queue.json'
DONE  = r'D:\roms\library\roms\_importre_state\completed.json'

with open(QUEUE, 'r', encoding='utf-8') as f:
    q = json.load(f)
queue = q.get('queue', [])

print("=== FORMATO ITENS PENDENTES ===")
for i in queue[:3]:
    print(json.dumps(i, ensure_ascii=False, indent=2)[:500])
    print("---")

# Verificar completed
try:
    with open(DONE, 'r', encoding='utf-8') as f:
        done = json.load(f)
    if isinstance(done, dict):
        done = done.get('completed', done.get('items', []))
    print(f"\n=== COMPLETADOS: {len(done)} ===")
    for i in done[:3]:
        print(json.dumps(i, ensure_ascii=False, indent=2)[:500])
        print("---")
except Exception as e:
    print(f"Erro lendo completed: {e}")

# Verificar se ha arquivo de seriais com nomes
import os
for fn in ['PSX_Colecao_Faltantes.md', 'psx_serials.json', 'serials_db.json']:
    p = os.path.join(r'D:\roms\library\roms\psx', fn)
    if os.path.exists(p):
        print(f"\nArquivo existe: {p} ({os.path.getsize(p)} bytes)")
