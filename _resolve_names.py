"""Resolve nomes dos seriais pendentes usando o indice local do psxdatacenter."""
import json

PSXDC = r'D:\roms\library\roms\_importre_state\psxdc_index.json'
QUEUE = r'D:\roms\library\roms\_importre_state\queue.json'

with open(PSXDC, 'r', encoding='utf-8') as f:
    psxdc = json.load(f)

# Inverter: serial -> nome
serial_to_name = {}
for region, games in psxdc.items():
    for name, serial in games.items():
        serial_to_name[serial] = name

print(f"Indice invertido: {len(serial_to_name)} seriais")

with open(QUEUE, 'r', encoding='utf-8') as f:
    q = json.load(f)
queue = q.get('queue', [])

print(f"\nPendentes: {len(queue)}")
resolved = {}
unresolved = []
for item in queue:
    s = item.get('serial', '')
    if s in serial_to_name:
        resolved[s] = serial_to_name[s]
        print(f"  OK  {s}: {serial_to_name[s]}")
    else:
        unresolved.append(s)
        print(f"  ??  {s}")

print(f"\nResolvidos: {len(resolved)} | Nao resolvidos: {len(unresolved)}")
print(f"\nNao resolvidos: {unresolved}")

# Salvar mapeamento
out = r'D:\roms\library\roms\psx\_serial_names_resolved.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(resolved, f, ensure_ascii=False, indent=2)
print(f"\nSalvo em: {out}")
