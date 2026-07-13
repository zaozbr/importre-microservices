import json

d = json.load(open(r'D:\roms\library\roms\_importre_state\cross_index_results.json'))
found = d['found']

ACCESSIBLE = {'redump_psx', 'CuratedPSXRedumpCHDs', 'Redump_PSX_2021_06_04_A_C'}
RESTRICTED_PREFIXES = ('Redump.orgSonyPlayStation-', 'psx-roms-archive')

accessible = []
restricted = []
unknown = []

for r in found:
    coll = r.get('collection', '')
    if coll in ACCESSIBLE:
        accessible.append(r)
    elif any(coll.startswith(p) for p in RESTRICTED_PREFIXES):
        restricted.append(r)
    else:
        unknown.append(r)

print(f"Total encontrados: {len(found)}")
print(f"  Acessiveis (HTTP 200): {len(accessible)}")
print(f"  Restritas (401/403): {len(restricted)}")
print(f"  Desconhecidas: {len(unknown)}")

print(f"\nColecoes desconhecidas:")
for r in unknown:
    print(f"  {r['collection']}: {r['serial']}")

# Listar acessiveis
print(f"\nROMs em colecoes ACESSIVEIS ({len(accessible)}):")
for r in accessible:
    size_mb = int(r.get('size', '0')) / 1024 / 1024 if r.get('size', '0').isdigit() else 0
    print(f"  {r['serial']}: {r['filename'][:50]} ({size_mb:.1f}MB) [{r['collection']}]")
