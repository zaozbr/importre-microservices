import json
q = json.load(open(r'D:\roms\library\roms\_importre_state\queue.json'))
c = q.get('completed', {})
print('Completed (recentes):')
items = []
for k, v in c.items():
    if isinstance(v, dict):
        ts = v.get('completed_at', 0)
        if not isinstance(ts, (int, float)):
            ts = 0
        items.append((k, v.get('site', '?'), ts))
    else:
        items.append((k, str(v), 0))
items.sort(key=lambda x: float(x[2]), reverse=True)
for k, site, ts in items[:10]:
    print(f'  {k}: site={site} ts={ts}')
