import json, re
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
FALTANTES = Path(r"D:\roms\library\roms\PSX_Colecao_Faltantes.md")
QUEUE = Path(r"D:\roms\library\roms\_importre_state\queue.json")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# CHDs existentes
chd_serials = set()
for c in PSX.glob("*.chd"):
    s = extract_serial(c.stem)
    if s: chd_serials.add(s)

# Faltantes
faltantes_serials = set()
if FALTANTES.exists():
    content = FALTANTES.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r'([A-Z]{2,4}[-]\d{3,5})', content):
        faltantes_serials.add(m.group(1).upper())

faltantes_sem_chd = faltantes_serials - chd_serials

# Carregar queue
with QUEUE.open(encoding="utf-8") as f:
    data = json.load(f)

queue = data.get("queue", [])
in_progress = data.get("in_progress", {})
completed = data.get("completed", {})

# Seriais já na fila/existentes
existing = set()
for item in queue:
    s = item.get("serial", "").upper()
    if s: existing.add(s)
for s in in_progress.keys():
    if s: existing.add(s.upper())
for s in completed.keys():
    if s: existing.add(s.upper())

missing = sorted(faltantes_sem_chd - existing)
print(f"Faltantes sem CHD: {len(faltantes_sem_chd)}")
print(f"Ja na fila: {len(existing & faltantes_sem_chd)}")
print(f"Adicionando: {len(missing)}")

for s in missing:
    queue.append({
        "serial": s,
        "title": s,
        "status": "pending",
        "priority": 1,
        "added": None,
        "retry_count": 0,
        "site_history": {},
        "sources": []
    })

data["queue"] = queue

with QUEUE.open("w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Total na fila agora: {len(queue)}")
