"""Limpa in_progress e retorna itens para a fila."""
import json

QUEUE = r'D:\roms\library\roms\_importre_state\queue.json'
with open(QUEUE, 'r', encoding='utf-8') as f:
    q = json.load(f)

ip = q.get('in_progress', {})
if isinstance(ip, dict):
    items = list(ip.values())
else:
    items = ip

queue = q.get('queue', [])
# Retornar itens de in_progress para a fila
for item in items:
    if isinstance(item, dict) and item.get('serial'):
        queue.append(item)

q['queue'] = queue
q['in_progress'] = {}  # dict, nao list!
q['failed'] = {}  # dict, nao list!

with open(QUEUE, 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=2)

print(f'Limpo: {len(items)} itens retornados para fila. pending={len(queue)} in_prog=0 fail=0')
