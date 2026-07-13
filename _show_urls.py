import json
d = json.load(open(r'D:\roms\library\roms\_importre_state\cross_index_results.json'))
for r in d['found'][:5]:
    print(f"{r['serial']}: {r['url']}")
    print(f"  collection: {r['collection']}")
    print(f"  filename: {r['filename']}")
    print()
