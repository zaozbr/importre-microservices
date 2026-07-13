import sys, urllib.request, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    html = urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=10).read().decode('utf-8', errors='replace')
    data = json.loads(html)
    print("importre status:")
    print(f"  queue: {len(data.get('queue', []))}")
    print(f"  in_progress: {len(data.get('in_progress', {}))}")
    print(f"  completed: {len(data.get('completed', {}))}")
    print(f"  failed: {len(data.get('failed', {}))}")
    dl = data.get('dl_progress', {})
    print(f"  downloads ativos: {len(dl)}")
    for k, v in list(dl.items())[:5]:
        status = v.get('status', '?')
        progress = v.get('progress', 0)
        print(f"    {k}: {status} {progress:.0f}%")
except Exception as e:
    print(f"Erro: {e}")
