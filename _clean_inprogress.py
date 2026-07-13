"""Limpa in_progress movendo itens de volta para a fila."""
import json
from pathlib import Path

qpath = Path(r"D:\roms\library\roms\_importre_state\queue.json")
with open(qpath, "r", encoding="utf-8") as f:
    q = json.load(f)

in_prog = q.get("in_progress", {})
queue = q.get("queue", [])
for serial, item in in_prog.items():
    if isinstance(item, dict):
        for k in ("_phase", "_current_site", "_detail", "_worker", "_started_at"):
            item.pop(k, None)
        queue.append(item)
q["in_progress"] = {}
q["queue"] = queue

with open(qpath, "w", encoding="utf-8") as f:
    json.dump(q, f, indent=2, ensure_ascii=False)

completed = len(q.get("completed", {}))
failed = len(q.get("failed", {}))
print(f"Limpo: {len(queue)} pendentes, {completed} completados, {failed} falhos")
