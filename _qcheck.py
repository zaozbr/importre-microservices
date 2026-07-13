import json, os
q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
print(f"pending: {len(q.get('queue', []))}")
print(f"completed: {len(q.get('completed', {}))}")
print(f"in_progress: {len(q.get('in_progress', {}))}")
print(f"failed: {len(q.get('failed', {}))}")

# Verificar dl_progress
dp = r"D:\roms\library\roms\_importre_state\dl_progress.json"
if os.path.exists(dp):
    d = json.load(open(dp, "r", encoding="utf-8"))
    if isinstance(d, dict):
        items = d.get("downloads", d.get("items", []))
        print(f"\ndl_progress: {len(items)} items")
        for item in items[:5]:
            if isinstance(item, dict):
                print(f"  {item.get('serial','?')}: {item.get('speed','?')} {item.get('status','?')}")
    else:
        print(f"dl_progress: {type(d)}")
