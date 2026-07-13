"""Reconstroi queue.json a partir de PSX_Colecao_Faltantes.md.
Preserva completed e failed existentes. Dedup contra colecao local."""
import json, re, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.resolve()))
from importre import parse_missing_list, check_in_collection, save_json, QUEUE_PATH

old_data = json.load(open(QUEUE_PATH)) if QUEUE_PATH.exists() else {}
completed = old_data.get('completed', {})
failed = old_data.get('failed', {})

items = parse_missing_list()
queue = []
skipped = 0
for item in items:
    serial = item['serial']
    name = item.get('name', '')
    # Pular demos (SLED-*, SCED-*) — raramente disponiveis e consomem tempo de busca
    if serial.startswith(('SLED-', 'SCED-')):
        skipped += 1
        continue
    if serial in completed:
        skipped += 1
        continue
    if serial in failed:
        queue.append(item)
        continue
    if check_in_collection(serial, name):
        skipped += 1
        continue
    queue.append(item)

new_data = {
    'queue': queue,
    'in_progress': {},
    'completed': completed,
    'failed': failed,
    'retry_count': {},
    'total': len(queue) + skipped,
    'skipped': skipped,
}
save_json(QUEUE_PATH, new_data)
print(f'Fila reconstruida: {len(queue)} pendentes, {len(completed)} completados, {len(failed)} falhos, {skipped} skipped')
