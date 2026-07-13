import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\roms\library\roms\psx')
from _chd_convert_v2 import scan_roms
items = scan_roms()
print(f"Itens do scan: {len(items)}")
cues = sum(1 for i in items if i['ext'] == '.cue')
bins = sum(1 for i in items if i['ext'] == '.bin')
ecms = sum(1 for i in items if i['ext'] == '.ecm')
print(f"  CUEs: {cues}")
print(f"  BINs: {bins}")
print(f"  ECMs: {ecms}")
for item in items[:15]:
    serial = item.get('serial') or ''
    name = item.get('name', '')[:50]
    print(f"  {item['ext']:>5} {serial:>12} {name}")
