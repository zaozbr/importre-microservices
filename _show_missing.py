import json
d = json.load(open(r'D:\roms\library\roms\_importre_state\missing_analysis.json'))
print(f'Total faltando: {len(d["really_missing"])}')
print(f'  Comerciais: {len(d["missing_commercial"])}')
print(f'  Homebrew: {len(d["missing_homebrew"])}')
print(f'  ESPM: {len(d["missing_espm"])}')
print()
print('Download temp:')
for s, sz in d['downloaded_temp'].items():
    print(f'  {s}: {sz/1024/1024:.1f}MB')
print()
# Listar comerciais por regiao
comm = d['missing_commercial']
regions = {}
for s in comm:
    prefix = s[:4]
    regions.setdefault(prefix, []).append(s)
print('Por regiao:')
for r, ss in sorted(regions.items()):
    print(f'  {r}: {len(ss)}')
