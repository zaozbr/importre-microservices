import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
r = Path(r'D:\roms\library\roms\psx\_duck_test_results.json')
data = json.loads(r.read_text(encoding='utf-8'))
# Remover FAILs que sao falso-positivos de shader cache
cleaned = {}
removed = 0
for k, v in data.items():
    if v['status'] == 'FAIL' and 'shader cache' in v['detail'].lower():
        removed += 1
        continue  # descartar para retestar
    if v['status'] == 'FAIL' and 'eacces' in v['detail'].lower():
        removed += 1
        continue
    if v['status'] == 'UNKNOWN' and 'no_indicators' in v['detail'].lower():
        removed += 1
        continue
    cleaned[k] = v
print(f'Removidos {removed} resultados falso-positivos')
print(f'Restantes: {len(cleaned)} (OK={sum(1 for v in cleaned.values() if v["status"]=="OK")}, FAIL={sum(1 for v in cleaned.values() if v["status"]=="FAIL")}, UNK={sum(1 for v in cleaned.values() if v["status"]=="UNKNOWN")})')
r.write_text(json.dumps(cleaned, indent=2), encoding='utf-8')
