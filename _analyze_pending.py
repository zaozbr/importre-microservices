"""Analisa perfil dos itens pendentes para planejar nova estrategia de busca."""
import json, os
from collections import Counter

QUEUE = r'D:\roms\library\roms\_importre_state\queue.json'
DONE  = r'D:\roms\library\roms\_importre_state\completed.json'

with open(QUEUE, 'r', encoding='utf-8') as f:
    q = json.load(f)
queue = q.get('queue', [])

# Categorias por prefixo de serial
cats = Counter()
samples = {}
for item in queue:
    s = item.get('serial', '')
    n = item.get('name', '')
    if s.startswith(('SLPS', 'SLPM', 'SCPS', 'SLKA', 'SLPSM')):
        cat = 'JP'
    elif s.startswith(('SLUS', 'SCUS', 'SLED')):
        cat = 'US'
    elif s.startswith(('SLES', 'SCES', 'SLED')):
        cat = 'EU'
    elif s.startswith(('HBREW', 'BREW')):
        cat = 'HB'
    elif s.startswith('NOSERIAL'):
        cat = 'NS'
    else:
        cat = 'OTHER'
    cats[cat] += 1
    if cat not in samples:
        samples[cat] = []
    if len(samples[cat]) < 8:
        samples[cat].append((s, n[:70]))

print("=== DISTRIBUICAO PENDENTES ===")
for cat, cnt in cats.most_common():
    print(f"  {cat}: {cnt}")
print(f"  TOTAL: {sum(cats.values())}")

print("\n=== AMOSTRAS POR CATEGORIA ===")
for cat, items in samples.items():
    print(f"\n[{cat}]")
    for s, n in items:
        print(f"  {s:20s} | {n}")

# Verificar quantos ja tem pre-search no buffer
buf_path = r'D:\roms\library\roms\_importre_state\presearch_buffer.json'
if os.path.exists(buf_path):
    with open(buf_path, 'r', encoding='utf-8') as f:
        buf = json.load(f)
    print(f"\n=== PRE-SEARCH BUFFER ===")
    print(f"  Itens no buffer: {len(buf)}")
else:
    print(f"\n  (sem buffer de pre-search)")

# Listar nomes unicos para inspirar estrategias
print("\n=== NOMES PENDENTES (primeiros 30 JP) ===")
jp_items = [i for i in queue if i.get('serial', '').startswith(('SLPS', 'SLPM', 'SCPS'))]
for i in jp_items[:30]:
    print(f"  {i.get('serial',''):20s} | {i.get('name','')[:70]}")
