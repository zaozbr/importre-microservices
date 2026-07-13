import json
with open(r'D:/roms/library/roms/_importre_state/sites.json', 'r') as f:
    sites = json.load(f)
print('Sites:')
for k, v in sites.items():
    print(f"{k}: enabled={v.get('enabled')}, fail_count={v.get('fail_count',0)}, max_fails={v.get('max_fails',50)}")
