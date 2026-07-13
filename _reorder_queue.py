"""Reordena a fila: seriais reais primeiro, NOSERIAL e homebrew no final."""
import json
from pathlib import Path

qpath = Path(r"D:\roms\library\roms\_importre_state\queue.json")
with open(qpath, "r", encoding="utf-8") as f:
    q = json.load(f)

queue = q.get("queue", [])
in_prog = q.get("in_progress", {})

# Mover itens presos em in_progress de volta para a fila
for serial, item in list(in_prog.items()):
    queue.append({"serial": serial, "name": item.get("name", ""), "type": item.get("type", "commercial"), "region": item.get("region", "")})
q["in_progress"] = {}

# Separar por categoria
real_serials = []
noserials = []
homebrews = []
others = []

for item in queue:
    serial = item.get("serial", "")
    if serial.startswith("NOSERIAL"):
        noserials.append(item)
    elif serial.startswith("HBREW") or serial.startswith("HOMEBREW") or serial.startswith("BREW"):
        homebrews.append(item)
    else:
        real_serials.append(item)

# Reordenar: seriais reais primeiro, depois homebrew, depois noserial
new_queue = real_serials + homebrews + noserials

q["queue"] = new_queue
q["skipped"] = 0

with open(qpath, "w", encoding="utf-8") as f:
    json.dump(q, f, indent=2, ensure_ascii=False)

print(f"Fila reordenada:")
print(f"  Serials reais: {len(real_serials)} (primeiros)")
print(f"  Homebrew: {len(homebrews)} (depois)")
print(f"  NOSERIAL: {len(noserials)} (por ultimo)")
print(f"  Total: {len(new_queue)}")
print(f"  In_progress limpo: {len(in_prog)} itens devolvidos")
