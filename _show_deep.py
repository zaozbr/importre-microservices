import json
d = json.load(open(r'D:\roms\library\roms\_importre_state\deep_search_v2_results.json'))
print(f'Found: {len(d["found"])}')
print(f'Not found: {len(d["not_found"])}')
for r in d['found'][:20]:
    print(f"  {r['serial']}: {r['identifier']} -> {r.get('filename', '?')[:40]}")
