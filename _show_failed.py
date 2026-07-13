import json
q = json.load(open(r'D:\roms\library\roms\_importre_state\queue.json'))
c = q.get('completed', {})
f = q.get('failed', {})
ip = q.get('in_progress', {})
pend = q.get('queue', [])
print(f'Completed: {len(c)}')
print(f'Failed: {len(f) if isinstance(f, dict) else f}')
print(f'InProgress: {len(ip) if isinstance(ip, dict) else ip}')
print(f'Pending: {len(pend)}')
print()
if isinstance(f, dict):
    print('Failed ROMs:')
    for serial, info in f.items():
        print(f'  {serial}: {str(info)[:80]}')
if isinstance(ip, dict):
    print('InProgress:')
    for serial, info in ip.items():
        print(f'  {serial}: {str(info)[:80]}')
