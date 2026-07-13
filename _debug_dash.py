"""Debug: verifica dados do dashboard."""
import json, urllib.request

r = urllib.request.urlopen("http://127.0.0.1:8765/api/status/fast", timeout=5)
data = json.loads(r.read())
items = data["status"]["in_progress_items"]
for serial, item in list(items.items())[:5]:
    print(f"{serial}:")
    print(f"  keys = {list(item.keys())}")
    print(f"  name = {item.get('name', 'MISSING')}")
    print(f"  _phase = {item.get('_phase', '?')}")
    print(f"  _current_site = {item.get('_current_site', '?')}")
    print(f"  _detail = {item.get('_detail', '?')[:60]}")
    print()

# Verificar dl_progress
dl = data["status"].get("dl_progress", {})
print(f"dl_progress items: {len(dl)}")
for serial, info in list(dl.items())[:3]:
    print(f"  {serial}: dl={info.get('downloaded',0)} total={info.get('total',0)} speed={info.get('speed',0)}")
