import sys, json; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
q = Path(r'D:\roms\library\roms\_importre_state\queue.json')
data = json.loads(q.read_text(encoding='utf-8'))
print(f'Keys: {list(data.keys())}')
print(f'Total: {data.get("total", "?")}')
print(f'Queue (pending): {len(data.get("queue", []))}')
print(f'In progress: {len(data.get("in_progress", {}))}')
print(f'Completed: {len(data.get("completed", {}))}')
print(f'Failed: {len(data.get("failed", {}))}')
print(f'Skipped (raw): {data.get("skipped", "?")}')

# Verificar se ha skip_list separado
skip_file = Path(r'D:\roms\library\roms\_importre_state\skip_list.json')
if skip_file.exists():
    skip_data = json.loads(skip_file.read_text(encoding='utf-8'))
    print(f'\nskip_list.json:')
    print(f'  Type: {type(skip_data)}')
    if isinstance(skip_data, dict):
        print(f'  Keys: {list(skip_data.keys())[:10]}')
        print(f'  Count: {len(skip_data)}')
        for k in list(skip_data.keys())[:5]:
            print(f'  {k}: {repr(skip_data[k])[:200]}')
    elif isinstance(skip_data, list):
        print(f'  Count: {len(skip_data)}')
        for s in skip_data[:5]:
            print(f'  {repr(s)[:200]}')
else:
    print(f'\nskip_list.json nao encontrado')

# Verificar blacklist
bl = Path(r'D:\roms\library\roms\_importre_state\blacklist.json')
if bl.exists():
    bl_data = json.loads(bl.read_text(encoding='utf-8'))
    print(f'\nblacklist.json: type={type(bl_data)}, count={len(bl_data) if hasattr(bl_data, "__len__") else "?"}')

# Verificar control
ctrl = Path(r'D:\roms\library\roms\_importre_state\control.json')
if ctrl.exists():
    ctrl_data = json.loads(ctrl.read_text(encoding='utf-8'))
    print(f'\ncontrol.json: {repr(ctrl_data)[:300]}')
