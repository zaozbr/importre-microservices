"""Limpa in_progress, re-enfileira falhas e atualiza nomes na fila."""
import json, os, sys
sys.path.insert(0, r'D:\roms\library\roms\psx')
from _deep_search import resolve_name

QUEUE = r'D:\roms\library\roms\_importre_state\queue.json'

with open(QUEUE, 'r', encoding='utf-8') as f:
    q = json.load(f)

# 1. Limpar in_progress (itens presos)
ip = q.get('in_progress', [])
queue = q.get('queue', [])
print(f"Antes: pending={len(queue)} in_prog={len(ip)} done={len(q.get('completed',[]))} fail={len(q.get('failed',[]))}")

# Mover in_progress de volta para queue
for item in ip:
    if isinstance(item, dict):
        s = item.get('serial', '')
        # Nao re-enfileirar se ja esta na fila
        if not any(i.get('serial') == s for i in queue):
            queue.append(item)

q['in_progress'] = []
print(f"Limpo in_progress: {len(ip)} itens devolvidos a fila")

# 2. Re-enfileirar falhas (com retry_count < 5)
failed = q.get('failed', [])
requeued = 0
still_failed = []
for item in failed:
    if isinstance(item, dict):
        retry = item.get('retry_count', 0)
        if retry < 5:
            item['retry_count'] = retry + 1
            s = item.get('serial', '')
            if not any(i.get('serial') == s for i in queue):
                queue.append(item)
                requeued += 1
            else:
                still_failed.append(item)
        else:
            still_failed.append(item)
q['failed'] = still_failed
print(f"Re-enfileiradas {requeued} falhas (retry < 5)")

# 3. Atualizar nomes vazios na fila
updated = 0
for item in queue:
    if isinstance(item, dict) and not item.get('name'):
        s = item.get('serial', '')
        if s and not s.startswith(('NOSERIAL', 'BREW')):
            name = resolve_name(s)
            if name:
                item['name'] = name
                updated += 1

print(f"Nomes resolvidos: {updated} itens")

q['queue'] = queue
with open(QUEUE, 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=2)

print(f"\nDepois: pending={len(queue)} in_prog=0 done={len(q.get('completed',[]))} fail={len(still_failed)}")
