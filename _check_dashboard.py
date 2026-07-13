"""Verifica dashboard importre via HTTP."""
import urllib.request, json

try:
    r = urllib.request.urlopen("http://127.0.0.1:8765/", timeout=10)
    html = r.read().decode("utf-8", errors="replace")
    print(f"Dashboard HTML: {len(html)} chars, status={r.status}")
    # Procurar por dados no HTML
    if "dl_progress" in html:
        print("  Contém dl_progress: SIM")
    if "completed" in html:
        print("  Contém completed: SIM")
    if "in_progress" in html:
        print("  Contém in_progress: SIM")
except Exception as e:
    print(f"Dashboard ERRO: {e}")

# API status
try:
    r = urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=10)
    d = json.loads(r.read())
    print(f"\nAPI /api/status: {json.dumps(d, indent=2, ensure_ascii=False)[:2000]}")
except Exception as e:
    print(f"\nAPI ERRO: {e}")

# API queue
try:
    r = urllib.request.urlopen("http://127.0.0.1:8765/api/queue", timeout=10)
    d = json.loads(r.read())
    if isinstance(d, dict):
        print(f"\nAPI /api/queue:")
        print(f"  pending: {len(d.get('queue', []))}")
        print(f"  completed: {len(d.get('completed', {}))}")
        print(f"  in_progress: {len(d.get('in_progress', {}))}")
        print(f"  failed: {len(d.get('failed', {}))}")
    elif isinstance(d, list):
        print(f"\nAPI /api/queue: {len(d)} items")
except Exception as e:
    print(f"\nAPI /api/queue ERRO: {e}")
