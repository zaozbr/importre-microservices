import json
with open(r'D:\roms\library\roms\_importre_state\learning.json', 'r') as f:
    data = json.load(f)
stats = data.get('site_stats', {})
for site, s in sorted(stats.items(), key=lambda x: x[1].get('success', 0), reverse=True):
    print(site, 'success=', s.get('success', 0), 'fail=', s.get('fail', 0), 'attempts=', s.get('attempts', 0))
