import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
r = Path(r'D:\roms\library\roms\psx\_duck_test_results.json')
data = json.loads(r.read_text(encoding='utf-8'))
ok = sum(1 for v in data.values() if v['status'] == 'OK')
fail = sum(1 for v in data.values() if v['status'] == 'FAIL')
unk = sum(1 for v in data.values() if v['status'] == 'UNKNOWN')
print(f'Total: {len(data)} | OK: {ok} | FAIL: {fail} | UNK: {unk}')
print()
fails = {k: v for k, v in data.items() if v['status'] == 'FAIL'}
for k, v in list(fails.items())[:15]:
    print(f'  {Path(k).name}: {v["detail"][:120]}')
print()
unks = {k: v for k, v in data.items() if v['status'] == 'UNKNOWN'}
for k, v in list(unks.items())[:5]:
    print(f'  UNK {Path(k).name}: {v["detail"][:120]}')
