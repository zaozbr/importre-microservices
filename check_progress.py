import json
with open(r'F:\importre_state\download_progress.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
print(f"Completed: {len(d.get('completed', {}))}")
print(f"Failed: {len(d.get('failed', {}))}")
print(f"Last index: {d.get('last_index', 0)}")
for k, v in list(d.get('completed', {}).items())[:10]:
    print(f"  OK: {k} -> {v.get('chd','')}")
for k, v in list(d.get('failed', {}).items())[:5]:
    print(f"  FAIL: {k} -> {v.get('reason','')}")
