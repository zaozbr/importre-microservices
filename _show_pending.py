import json
q = json.load(open(r'D:\roms\library\roms\_importre_state\queue.json','r',encoding='utf-8'))
p = q.get('queue', [])
ip = q.get('in_progress', {})
d = q.get('completed', {})
f = q.get('failed', {})
print(f'pending={len(p)} in_prog={len(ip)} done={len(d)} fail={len(f)}')
print('\nPendentes:')
for item in p:
    if isinstance(item, dict):
        s = item.get('serial', '')
        n = item.get('name', '')[:40]
        print(f'  {s}: {n}')
