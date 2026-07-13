"""Verifica estrutura detalhada da API /api/status."""
import urllib.request, json

r = urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=10)
d = json.loads(r.read())

status = d.get("status", {})
print("=== STATUS keys ===")
for k, v in status.items():
    if isinstance(v, dict):
        print(f"  {k}: dict({len(v)} keys)")
        # Mostrar algumas subkeys
        for sk, sv in list(v.items())[:3]:
            if isinstance(sv, dict):
                print(f"    {sk}: dict({len(sv)} keys)")
            elif isinstance(sv, list):
                print(f"    {sk}: list({len(sv)} items)")
            else:
                print(f"    {sk}: {repr(sv)[:80]}")
    elif isinstance(v, list):
        print(f"  {k}: list({len(v)} items)")
        if v and isinstance(v[0], dict):
            print(f"    first item keys: {list(v[0].keys())[:5]}")
    else:
        print(f"  {k}: {repr(v)[:100]}")

# Verificar dl_progress especificamente
dl = status.get("dl_progress", [])
print(f"\n=== dl_progress: {len(dl)} items ===")
for item in dl[:5]:
    if isinstance(item, dict):
        print(f"  {item.get('serial','?')}: speed={item.get('speed','?')} status={item.get('status','?')} pct={item.get('pct','?')}")

# Verificar queue dentro de status
q = status.get("queue", {})
if isinstance(q, dict):
    print(f"\n=== queue: {len(q)} keys ===")
    for k, v in q.items():
        if isinstance(v, (list, dict)):
            print(f"  {k}: {type(v).__name__}({len(v)})")
        else:
            print(f"  {k}: {v}")
