"""Verifica o conteudo do status no dashboard."""
import json, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

r = urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=5)
data = json.loads(r.read())
status = data['status']
print('status keys:', list(status.keys()))
print()
for k, v in status.items():
    if isinstance(v, (dict, list)):
        length = len(v) if hasattr(v, '__len__') else '?'
        print(f'{k}: {type(v).__name__} len={length}')
        if isinstance(v, list) and v:
            print(f'  sample: {json.dumps(v[0], ensure_ascii=False)[:200]}')
        elif isinstance(v, dict) and v:
            first_key = list(v.keys())[0]
            print(f'  sample [{first_key}]: {json.dumps(v[first_key], ensure_ascii=False)[:200]}')
    else:
        print(f'{k}: {repr(v)[:150]}')
