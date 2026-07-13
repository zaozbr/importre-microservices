"""
Sincroniza queue.json com arquivos ja baixados em downloads/.
Marca itens como completed se o arquivo correspondente ja existe.
"""
import json, os, re

STATE = r'D:\roms\library\roms\_importre_state'
QUEUE = os.path.join(STATE, 'queue.json')
DOWNLOADS = os.path.join(STATE, 'downloads')

# Listar arquivos baixados
downloaded_serials = set()
if os.path.exists(DOWNLOADS):
    for fn in os.listdir(DOWNLOADS):
        # Arquivos temporarios nao contam
        if any(fn.endswith(ext) for ext in ('.part', '.tmp', '.crdownload', '.download')):
            continue
        # Extrair serial do nome do arquivo (antes do primeiro _)
        # Formato: SERIAL_NomeDoJogo.ext
        match = re.match(r'^([A-Z]+-\d+)', fn)
        if match:
            downloaded_serials.add(match.group(1))
        else:
            # Tentar outros formatos (BREW-xxx, NOSERIAL-xxx)
            match2 = re.match(r'^([A-Z]+-[A-F0-9]+)', fn)
            if match2:
                downloaded_serials.add(match2.group(1))

print(f"Arquivos baixados: {len(downloaded_serials)} seriais unicos")
print(f"Amostra: {list(downloaded_serials)[:10]}")

# Carregar fila
with open(QUEUE, 'r', encoding='utf-8') as f:
    q = json.load(f)

queue = q.get('queue', [])
completed = q.get('completed', {})
if not isinstance(completed, dict):
    completed = {}
in_progress = q.get('in_progress', [])
failed = q.get('failed', [])

# Marcar como completed os itens que ja tem arquivo baixado
already_completed_serials = set(completed.keys())

newly_completed = {}
new_queue = []
for item in queue:
    s = item.get('serial', '') if isinstance(item, dict) else ''
    if s in downloaded_serials and s not in already_completed_serials:
        newly_completed[s] = item
    else:
        new_queue.append(item)

# Tambem remover de in_progress e failed os que ja tem arquivo
new_in_progress = [i for i in in_progress if (i.get('serial','') if isinstance(i, dict) else '') not in downloaded_serials]
new_failed = [i for i in failed if (i.get('serial','') if isinstance(i, dict) else '') not in downloaded_serials]

print(f"\nAntes: pending={len(queue)} in_prog={len(in_progress)} done={len(completed)} fail={len(failed)}")
print(f"Novos completados: {len(newly_completed)}")
print(f"Removidos de in_progress: {len(in_progress)-len(new_in_progress)}")
print(f"Removidos de failed: {len(failed)-len(new_failed)}")

q['queue'] = new_queue
q['completed'] = {**completed, **newly_completed}
q['in_progress'] = new_in_progress
q['failed'] = new_failed

with open(QUEUE, 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=2)

print(f"\nDepois: pending={len(new_queue)} in_prog={len(new_in_progress)} done={len(q['completed'])} fail={len(new_failed)}")
