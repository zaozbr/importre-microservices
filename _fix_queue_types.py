"""Corrige tipos no queue.json para compatibilidade com importre.py"""
import json

QUEUE = r'D:\roms\library\roms\_importre_state\queue.json'
with open(QUEUE, 'r', encoding='utf-8') as f:
    q = json.load(f)

# in_progress deve ser dict {serial: item}
ip = q.get('in_progress', [])
if isinstance(ip, list):
    new_ip = {}
    for item in ip:
        if isinstance(item, dict):
            s = item.get('serial', '')
            if s:
                new_ip[s] = item
    q['in_progress'] = new_ip
    print(f'in_progress: list({len(ip)}) -> dict({len(new_ip)})')

# failed deve ser dict {serial: item}
fl = q.get('failed', [])
if isinstance(fl, list):
    new_fl = {}
    for item in fl:
        if isinstance(item, dict):
            s = item.get('serial', '')
            if s:
                new_fl[s] = item
    q['failed'] = new_fl
    print(f'failed: list({len(fl)}) -> dict({len(new_fl)})')

# retry_count deve ser dict
rc = q.get('retry_count')
if rc is None or isinstance(rc, list):
    q['retry_count'] = {}
    print(f'retry_count: {type(rc).__name__} -> dict')

# completed ja e dict
c = q.get('completed', {})
if not isinstance(c, dict):
    new_c = {}
    if isinstance(c, list):
        for item in c:
            if isinstance(item, dict):
                s = item.get('serial', '')
                if s:
                    new_c[s] = item
    q['completed'] = new_c
    print(f'completed: {type(c).__name__} -> dict({len(new_c)})')
else:
    print(f'completed: dict({len(c)}) OK')

with open(QUEUE, 'w', encoding='utf-8') as f:
    json.dump(q, f, ensure_ascii=False, indent=2)

print('queue.json corrigido!')
