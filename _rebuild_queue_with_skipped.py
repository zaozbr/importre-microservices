"""Reconstroi queue.json a partir de PSX_Colecao_Faltantes.md.
Coloca skipped (ja na colecao) e failed no FIM da fila, para serem tentados novamente.
Preserva completed. Homebrew nao gera serial no nome do arquivo (HBREW so referencia)."""
import json
import re
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.resolve()))
from importre import parse_missing_list, check_in_collection, save_json, QUEUE_PATH

old_data = json.load(open(QUEUE_PATH)) if QUEUE_PATH.exists() else {}
completed = old_data.get('completed', {})
failed = old_data.get('failed', {})

items = parse_missing_list()
queue = []
skipped = []
failed_list = []

for item in items:
    serial = item.get('serial')
    name = item.get('name', '')
    # Failed: colocar no fim
    if serial and serial in failed:
        failed_list.append(item)
        continue
    # Completed: manter fora
    if serial and serial in completed:
        continue
    # Ja na colecao? -> skipped, vai para o fim
    if check_in_collection(serial, name):
        skipped.append(item)
        continue
    # Normal: inicio da fila
    queue.append(item)

# Skipped e failed vao para o final
queue.extend(failed_list)
queue.extend(skipped)

new_data = {
    'queue': queue,
    'in_progress': {},
    'completed': completed,
    'failed': {},
    'retry_count': {},
    'total': len(queue) + len(completed) + len(failed),
    'skipped': len(skipped),
}
# Manter failed original fora da fila, mas para referencia
new_data['failed'] = failed
save_json(QUEUE_PATH, new_data)
print(f'Fila reconstruida: {len(queue)} pendentes (skipped+failed no fim), {len(completed)} completados, {len(failed)} falhos, {len(skipped)} skipped')
