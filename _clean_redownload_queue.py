"""Limpa a fila de redownload: remove lixo e duplicados."""
import json, time
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

QUEUE_FILE = r'D:\roms\library\roms\_importre_state\queue.json'
q = json.load(open(QUEUE_FILE, 'r', encoding='utf-8'))
queue = q['queue']
print(f'Antes: {len(queue)} itens')

# Padrões de lixo
garbage_patterns = [
    '_temp_', 'UNKNOWN', 'test-chd', '_old_scan', 'buzzy', 'WCG2', 'SBL0',
    'DS84LH', 'yicestar', 'japan-j3', 'We11World', 'Marilyn-In-the-Magic',
    'White-Diamond.chd', 'Nazo-Oh', 'Cyberspeed-The-Future',
    'PSX - Clay Fighter', 'Retrouve-la-Magie-Disney',
]

cleaned = []
removed = 0
for item in queue:
    serial = item.get('serial', '')
    name = item.get('name', '')
    is_garbage = False
    for p in garbage_patterns:
        if p in serial or p in name:
            is_garbage = True
            break
    if is_garbage:
        removed += 1
        print(f'  REMOVIDO: {serial} | {name[:50]}')
    else:
        cleaned.append(item)

# Deduplicar por serial
seen = set()
deduped = []
dupes = 0
for item in cleaned:
    s = item.get('serial', '')
    if s in seen:
        dupes += 1
        print(f'  DUPE: {s} | {item.get("name", "")[:50]}')
        continue
    seen.add(s)
    deduped.append(item)

q['queue'] = deduped
q['total'] = len(deduped) + len(q.get('completed', {})) + len(q.get('failed', {}))
json.dump(q, open(QUEUE_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'\nRemovidos (lixo): {removed}')
print(f'Duplicados removidos: {dupes}')
print(f'Final: {len(deduped)} itens na fila')
