"""Verifica o que o servidor importre retorna na API."""
import json, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    r = urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=5)
    data = json.loads(r.read())
    print('Keys:', list(data.keys()))
    print()
    for k in data:
        v = data[k]
        if isinstance(v, (dict, list)):
            length = len(v) if hasattr(v, '__len__') else '?'
            print(f'{k}: {type(v).__name__} len={length}')
        else:
            print(f'{k}: {repr(v)[:100]}')
except Exception as e:
    print(f'Erro: {e}')
