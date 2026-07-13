"""Drena itens presos em in_progress de volta para a fila."""
import json, time, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

QF = r'D:\roms\library\roms\_importre_state\queue.json'
q = json.load(open(QF, 'r', encoding='utf-8'))

ip = q.get('in_progress', {})
queue = q.get('queue', [])

print(f'Antes: {len(queue)} na fila, {len(ip)} em progresso')

# Mover todos os in_progress de volta para a fila
for serial, item in ip.items():
    if isinstance(item, dict):
        # Limpar campos de estado
        for key in ['_phase', '_current_site', '_detail', '_lock_ts', '_started_at']:
            item.pop(key, None)
        queue.append(item)

q['queue'] = queue
q['in_progress'] = {}
q['total'] = len(queue) + len(q.get('completed', {})) + len(q.get('failed', {}))

json.dump(q, open(QF, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

print(f'Depois: {len(queue)} na fila, 0 em progresso')
print(f'Total: {q["total"]}')
