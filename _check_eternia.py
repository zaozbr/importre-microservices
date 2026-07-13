import json
from pathlib import Path
q = Path(r"D:\roms\library\roms\_importre_state\queue.json")
data = json.loads(q.read_text(encoding="utf-8"))
items = data if isinstance(data, list) else data.get("items", data.get("queue", []))
print(f"Total na fila: {len(items)}")
matches = [i for i in items if "eternia" in str(i).lower()]
print(f"Matches Eternia: {len(matches)}")
for i in matches:
    title = i.get("title", "?")[:60]
    status = i.get("status", "?")
    serial = i.get("serial", "?")
    print(f"  {title:60s} | status={status} | serial={serial}")
