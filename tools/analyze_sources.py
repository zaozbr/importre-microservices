import os, sys
from collections import Counter

p = 'D:/roms/library/roms/_importre_state/importre.log'
sz = os.path.getsize(p)
start = max(0, sz - 1024*1024)
data = open(p, 'rb').read()[start:].decode('utf-8', 'ignore').splitlines()

ready = [l for l in data if 'Ready ' in l and 'fontes' in l]
c = Counter()
for l in ready:
    parts = l.split('fontes (')
    if len(parts) > 1:
        sites = parts[1].rstrip(')')
        for s in sites.split(', '):
            c[s.strip()] += 1

print('Fontes por site (ultimas buscas):')
for k, v in c.most_common(20):
    print(f'  {k}: {v}')

# Tambem conta erros por plugin
errors = [l for l in data if 'Plugin error' in l or 'Nao foi possivel' in l]
ec = Counter()
for l in errors:
    if 'Plugin error' in l:
        # "Plugin error <name> <msg>"
        parts = l.split('Plugin error ')
        if len(parts) > 1:
            name = parts[1].split(' ')[0]
            ec[name] += 1
print('\nErros por plugin:')
for k, v in ec.most_common(20):
    print(f'  {k}: {v}')
