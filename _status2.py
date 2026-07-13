import json
with open(r'D:\roms\library\roms\_importre_state\queue.json','r',encoding='utf-8') as f:
    q=json.load(f)
p=len(q.get('queue',[]))
ip=len(q.get('in_progress',[]))
d=len(q.get('completed',[]))
f=len(q.get('failed',[]))
print(f'pending={p} in_prog={ip} done={d} fail={f}')
done = q.get('completed', [])
if done:
    print('Ultimos completados:')
    for item in done[-5:]:
        if isinstance(item, dict):
            s = item.get('serial','')
            n = item.get('name','')[:50]
            print(f'  {s}: {n}')
