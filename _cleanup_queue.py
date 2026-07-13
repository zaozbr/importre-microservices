"""
Limpa in_progress travado e reprocessa falhas do queue original.
Move falhas e in_progress de volta para a fila para o importre.py processar.
"""
import json, time

QUEUE_PATH = r'D:\roms\library\roms\_importre_state\queue.json'

with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
    q = json.load(f)

completed = q.get('completed', {})
if not isinstance(completed, dict):
    completed = {}

failed = q.get('failed', {})
if not isinstance(failed, dict):
    failed = {}

in_progress = q.get('in_progress', {})
if not isinstance(in_progress, dict):
    in_progress = {}

pending = q.get('queue', [])

# Mover falhas e in_progress de volta para pending
requeued = []

# Falhas (exceto "nao encontrado" que vao voltar para busca)
for serial, info in failed.items():
    if isinstance(info, dict):
        reason = info.get('reason', '')
        if reason == 'nao encontrado':
            # Estas vao voltar para busca no importre
            continue
    # Outras falhas: requeue
    name = info.get('name', '') if isinstance(info, dict) else ''
    requeued.append({'serial': serial, 'name': name})

# In_progress travado
for serial, info in in_progress.items():
    name = info.get('name', '') if isinstance(info, dict) else ''
    requeued.append({'serial': serial, 'name': name})

# Adicionar requeued ao pending (evitar duplicatas)
existing_serials = {item['serial'] for item in pending if isinstance(item, dict) and 'serial' in item}
for item in requeued:
    if item['serial'] not in existing_serials and item['serial'] not in completed:
        pending.append(item)
        existing_serials.add(item['serial'])

# Limpar failed e in_progress
q['failed'] = {}
q['in_progress'] = {}
q['queue'] = pending

with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=2)

print(f"Requeued: {len(requeued)}")
print(f"Pending: {len(pending)}")
print(f"Completed: {len(completed)}")
print(f"Failed: 0 (limpo)")
print(f"InProgress: 0 (limpo)")
