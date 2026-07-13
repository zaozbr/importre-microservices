import json
d = json.load(open(r'D:\roms\library\roms\_importre_state\cross_index_results.json'))
print(f'Encontrados: {len(d["found"])}')
print(f'Nao encontrados: {len(d["not_found"])}')
types = {}
for r in d['found']:
    t = r.get('match_type', '?')
    types[t] = types.get(t, 0) + 1
print(f'Por tipo: {types}')
colls = {}
for r in d['found']:
    c = r.get('collection', '?')[:40]
    colls[c] = colls.get(c, 0) + 1
print(f'Por colecao:')
for c, n in sorted(colls.items(), key=lambda x: -x[1]):
    print(f'  {c}: {n}')
