"""Verifica quais pendentes estao no indice JP e quais nao estao."""
import json

QUEUE = r'D:\roms\library\roms\_importre_state\queue.json'
IDX   = r'D:\roms\library\roms\_importre_state\archive_jp_index.json'
PUB   = r'D:\roms\library\roms\_importre_state\archive_jp_public_index.json'

with open(QUEUE, 'r', encoding='utf-8') as f:
    q = json.load(f)
queue = q.get('queue', [])

with open(IDX, 'r', encoding='utf-8') as f:
    idx = json.load(f)

try:
    with open(PUB, 'r', encoding='utf-8') as f:
        pub = json.load(f)
except:
    pub = {}

print(f"Indice JP: {len(idx)} | Indice public: {len(pub)}")
print(f"Pendentes: {len(queue)}")
print()

in_idx = []
not_in_idx = []
for item in queue:
    s = item.get('serial', '')
    if s in idx:
        in_idx.append((s, idx[s]))
    elif s in pub:
        in_idx.append((s, pub[s]))
    else:
        not_in_idx.append(s)

print(f"NO INDICE ({len(in_idx)}):")
for s, info in in_idx:
    print(f"  {s}: {info.get('file','')[:80]}")

print(f"\nFORA DO INDICE ({len(not_in_idx)}):")
for s in not_in_idx:
    print(f"  {s}")
