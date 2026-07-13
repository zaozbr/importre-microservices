"""Re-enfileira itens presos em in_progress (phase=starting sem URL)."""
import json, os, time

qpath = r"D:\roms\library\roms\_importre_state\queue.json"
q = json.load(open(qpath, "r", encoding="utf-8"))

ip = q.get("in_progress", {})
queue = q.get("queue", [])

moved = 0
to_remove = []
for serial, info in list(ip.items()):
    if isinstance(info, dict):
        phase = info.get("_phase", "")
        url = info.get("download_url", "")
        # Itens presos em starting sem URL, ou sem fase definida
        if phase == "starting" or (not url and phase in ("", "starting", "searching")):
            to_remove.append(serial)

for serial in to_remove:
    item = ip.pop(serial)
    # Re-enfileirar no final da fila
    queue.append({"serial": serial, "retry": item.get("retry", 0), "err": item.get("err", "")})
    moved += 1

q["in_progress"] = ip
q["queue"] = queue

# Backup
import shutil
shutil.copy2(qpath, qpath + ".bak_stuck")

json.dump(q, open(qpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Re-enfileirados: {moved}")
print(f"pending={len(queue)} ip={len(ip)} done={len(q.get('completed',{}))} fail={len(q.get('failed',{}))}")
