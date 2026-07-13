import json
q = json.load(open(r'D:\roms\library\roms\_importre_state\queue.json', encoding='utf-8'))
f = q.get('failed', {})
print(f"Falhas: {len(f)}")
for k, v in f.items():
    reason = v.get('reason', '?') if isinstance(v, dict) else str(v)
    name = v.get('name', '') if isinstance(v, dict) else ''
    print(f"  {k}: {reason} - {name}")

# Verificar in_progress
ip = q.get('in_progress', {})
print(f"\nIn Progress: {len(ip)}")
for k, v in ip.items():
    print(f"  {k}: {v}")

# Verificar se ha mais ROMs na colecao original
import os
col_path = r'D:\roms\library\roms\psx\PSX_Colecao_Faltantes.md'
if os.path.exists(col_path):
    with open(col_path, 'r', encoding='utf-8') as cf:
        lines = [l.strip() for l in cf if l.strip() and not l.startswith('#')]
    print(f"\nColecao original: {len(lines)} itens")
    completed = q.get('completed', {})
    missing = [l for l in lines if l.split('|')[0].strip() not in completed]
    print(f"Faltando baixar: {len(missing)}")
    for m in missing[:20]:
        print(f"  {m}")
