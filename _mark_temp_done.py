"""Marca downloads temporarios completos como completed no queue.json."""
import os, json, time

STATE_DIR = r'D:\roms\library\roms\_importre_state'
QUEUE_PATH = os.path.join(STATE_DIR, 'queue.json')
DOWNLOADS_DIR = os.path.join(STATE_DIR, 'downloads')

# Tamanhos esperados
EXPECTED = {
    'SLES-03328': 243492521,  # Jetracer (EU).zip
    'SLPM-86888': 52009886,   # playstationdisc.chd
    'SLPS-02427': 448786183,  # playstationdisc.chd
    'SLUS-01527': 1997067,    # playstationdisc.chd
}

NAMES = {
    'SLES-03328': 'JETRACER',
    'SLPM-86888': 'MOMOTAROU MATSURI',
    'SLPS-02427': 'TANTEI JINGUUJI SABURO',
    'SLUS-01527': 'BIG LEAGUE SLUGGERS BASEBALL',
}

with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
    q = json.load(f)

completed = q.get('completed', {})
if not isinstance(completed, dict):
    completed = {}

for serial, expected_size in EXPECTED.items():
    dest = os.path.join(DOWNLOADS_DIR, f'{serial}.download')
    if os.path.exists(dest):
        actual_size = os.path.getsize(dest)
        pct = 100 * actual_size / expected_size if expected_size > 0 else 0
        print(f'{serial}: {actual_size/1024/1024:.1f}MB / {expected_size/1024/1024:.1f}MB ({pct:.0f}%)')
        if actual_size >= expected_size * 0.95:  # 95% = completo
            completed[serial] = {
                'serial': serial,
                'name': NAMES.get(serial, ''),
                'site': 'manual_download',
                'completed_at': time.time(),
            }
            print(f'  -> marcado como completed')
        else:
            print(f'  -> incompleto, nao marcar')
    else:
        print(f'{serial}: arquivo nao encontrado')

# Remover da fila e failed
queue = q.get('queue', [])
ip = q.get('in_progress', {})
if not isinstance(ip, dict):
    ip = {}
fl = q.get('failed', {})
if not isinstance(fl, dict):
    fl = {}

for serial in EXPECTED:
    queue = [item for item in queue if not (isinstance(item, dict) and item.get('serial') == serial)]
    ip.pop(serial, None)
    fl.pop(serial, None)

q['queue'] = queue
q['completed'] = completed
q['in_progress'] = ip
q['failed'] = fl

with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=2)

print(f'\nQueue atualizado. Completed: {len(completed)}')
