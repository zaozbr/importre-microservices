import json
q = json.load(open(r'D:\roms\library\roms\_importre_state\queue.json','r',encoding='utf-8'))
queue = q.get('queue', [])
completed = q.get('completed', {})
failed = q.get('failed', {})

# Deduplicar por serial, mantendo ordem
seen = set()
new_queue = []
for item in queue:
    if isinstance(item, dict):
        s = item.get('serial', '')
        if s and s not in seen and s not in completed:
            seen.add(s)
            new_queue.append(item)

q['queue'] = new_queue
q['in_progress'] = {}
q['failed'] = {}
json.dump(q, open(r'D:\roms\library\roms\_importre_state\queue.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'Dedup: {len(queue)} -> {len(new_queue)} pendentes')
