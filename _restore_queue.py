"""Restaura queue.json do backup mais recente e reconstroi."""
import json
from pathlib import Path
import re

STATE = Path(r"D:\roms\library\roms\_importre_state")
QUEUE_PATH = STATE / "queue.json"

# 1. Verificar backup mais recente
bak_path = STATE / "queue.json.bak12"
with open(bak_path, "r", encoding="utf-8") as f:
    q = json.load(f)

print(f"Backup bak12: queue={len(q.get('queue', []))} completed={len(q.get('completed', {}))} total={q.get('total', 0)}")

# 2. Verificar itens ja no disco (PSX_DIR)
import os
PSX_DIR = Path(r"D:\roms\library\roms\psx")
serial_pattern = re.compile(r'(SLUS|SLES|SCES|SLPS|SLPM|SCPS|SCUS|SLKA|SCED|BREW|HBREW|ESPM|HOMEBREW|NOSERIAL)[-_]?(\d{4,5})', re.I)

existing_serials = set()
for f in PSX_DIR.iterdir():
    m = serial_pattern.search(f.name)
    if m:
        serial = f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
        existing_serials.add(serial)
for d in PSX_DIR.iterdir():
    if d.is_dir():
        for f in d.iterdir():
            m = serial_pattern.search(f.name)
            if m:
                serial = f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
                existing_serials.add(serial)

print(f"Serials no disco: {len(existing_serials)}")

# 3. Remover da fila itens que ja estao no disco ou completed
queue = q.get("queue", [])
completed = q.get("completed", {})
new_queue = []
removed = 0
for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else ""
    if serial in existing_serials or serial in completed:
        removed += 1
        continue
    new_queue.append(item)

print(f"Itens removidos (ja no disco/completed): {removed}")
print(f"Nova fila: {len(new_queue)} itens")

# 4. Tambem verificar itens completed do backup
# Adicionar completed do backup atual se forem mais
current_q = {}
if QUEUE_PATH.exists():
    try:
        with open(QUEUE_PATH, "r", encoding="utf-8") as f:
            current_q = json.load(f)
    except:
        pass

# Merge completed: usar o maior set
current_completed = current_q.get("completed", {})
bak_completed = q.get("completed", {})
if len(current_completed) > len(bak_completed):
    final_completed = current_completed
else:
    final_completed = bak_completed

# 5. Salvar
q["queue"] = new_queue
q["completed"] = final_completed
q["in_progress"] = {}
q["failed"] = {}
q["retry_count"] = {}
q["skipped"] = 0
q["total"] = len(new_queue) + len(final_completed)

with open(QUEUE_PATH, "w", encoding="utf-8") as f:
    json.dump(q, f, indent=2, ensure_ascii=False)

print(f"Queue restaurado: pending={len(new_queue)} completed={len(final_completed)} total={q['total']}")
