"""Verifica itens skipped e re-enfileira os que realmente faltam no disco."""
import json
import re
from pathlib import Path

PSX_DIR = Path(r"D:\roms\library\roms\psx")
STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
QUEUE_PATH = STATE_DIR / "queue.json"
FALTANTES_PATH = Path(r"D:\roms\library\roms\PSX_Colecao_Faltantes.md")

# Carregar lista de faltantes
with open(FALTANTES_PATH, "r", encoding="utf-8") as f:
    faltantes_text = f.read()

# Extrair todos os seriais da lista de faltantes
serial_pattern = re.compile(r'(SLUS|SLES|SCES|SLPS|SLPM|SCPS|SCUS|SLKA|SCED|BREW|HBREW|ESPM|HOMEBREW)[-_]?(\d{4,5})', re.I)
faltantes_serials = set()
for m in serial_pattern.finditer(faltantes_text):
    serial = f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
    faltantes_serials.add(serial)

print(f"Serials na lista de faltantes: {len(faltantes_serials)}")

# Verificar quais ja existem no disco (como .chd, .bin, .iso, .img, etc)
existing_serials = set()
for f in PSX_DIR.iterdir():
    m = serial_pattern.search(f.name)
    if m:
        serial = f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
        existing_serials.add(serial)

print(f"Serials no disco (PSX_DIR): {len(existing_serials)}")

# Tambem verificar subdiretorios
for d in PSX_DIR.iterdir():
    if d.is_dir():
        for f in d.iterdir():
            m = serial_pattern.search(f.name)
            if m:
                serial = f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
                existing_serials.add(serial)

print(f"Serials no disco (total): {len(existing_serials)}")

# Itens que estao na lista de faltantes mas NAO estao no disco
realmente_faltantes = faltantes_serials - existing_serials
print(f"Realmente faltantes: {len(realmente_faltantes)}")

# Carregar queue.json
with open(QUEUE_PATH, "r", encoding="utf-8") as f:
    q = json.load(f)

queue = q.get("queue", [])
completed = q.get("completed", {})
in_queue = set()
for item in queue:
    if isinstance(item, dict):
        in_queue.add(item.get("serial", ""))
for serial in completed:
    in_queue.add(serial)

# Re-enfileirar itens que estao na lista de faltantes, nao estao no disco, e nao estao na fila
added = 0
for serial in realmente_faltantes:
    if serial not in in_queue:
        # Extrair nome do faltantes
        # Procurar o serial no texto
        idx = faltantes_text.find(serial)
        if idx >= 0:
            line = faltantes_text[idx:idx+200].split("\n")[0]
            name = line.replace(serial, "").strip(" -|")
        else:
            name = ""
        queue.append({"serial": serial, "name": name, "type": "commercial"})
        added += 1

q["queue"] = queue
q["skipped"] = 0  # Zerar skipped
q["total"] = len(queue) + len(q.get("in_progress", {})) + len(completed) + len(q.get("failed", {}))

with open(QUEUE_PATH, "w", encoding="utf-8") as f:
    json.dump(q, f, indent=2, ensure_ascii=False)

print(f"Re-enfileirados: {added}")
print(f"Novo total: pending={len(queue)}, completed={len(completed)}, total={q['total']}")
