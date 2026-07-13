import json
s = json.load(open(r'D:\roms\library\roms\_importre_state\sites.json'))
for k, v in sorted(s.items()):
    print(f"{k}: enabled={v.get('enabled')} fail={v.get('fail_count',0)} url={v.get('url','')}")
