"""Reconstrói a fila a partir da coleção faltante, verificando o que já existe no disco."""
import json, os, re

STATE = r"D:\roms\library\roms\_importre_state"
DLDIR = os.path.join(STATE, "downloads")

# 1. Carregar coleção faltante
faltantes_path = r"D:\roms\library\roms\PSX_Colecao_Faltantes.md"
if not os.path.exists(faltantes_path):
    print("PSX_Colecao_Faltantes.md não encontrado!")
    exit(1)

with open(faltantes_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Parse: formato tabela markdown | # | Serial | Nome |
faltantes = []
for line in lines:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("|---") or line.startswith("| #"):
        continue
    if line.startswith("|"):
        # Formato: | 1 | ESPM-70002 | Robots - Video Alchemy |
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]  # remover vazios
        if len(parts) >= 3:
            idx = parts[0]
            serial = parts[1]
            name = parts[2]
            if serial and serial != "Serial" and not serial.startswith("---"):
                region = "JP" if serial.startswith(("SLPM", "SLPS", "SCPS", "SIPS")) else \
                         "EU" if serial.startswith(("SLES", "SCED")) else \
                         "US" if serial.startswith(("SLUS", "SCUS")) else ""
                faltantes.append({"serial": serial, "name": name, "region": region})

print(f"Total na coleção faltante: {len(faltantes)}")

# 2. Verificar o que já existe no disco
existing_files = set(os.listdir(DLDIR)) if os.path.exists(DLDIR) else set()
existing_serials = set()
for f in existing_files:
    # Arquivos têm formato SERIAL_nome.ext
    m = re.match(r'^([A-Z]+-\d+)_', f)
    if m:
        existing_serials.add(m.group(1))

print(f"Serials no disco: {len(existing_serials)}")

# 3. Carregar queue atual
q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
completed = set(q.get("completed", {}).keys()) if isinstance(q.get("completed"), dict) else set()
failed = q.get("failed", {})
in_progress = q.get("in_progress", {})

print(f"Completed no queue: {len(completed)}")
print(f"Failed no queue: {len(failed)}")

# 4. Reconstruir fila — apenas itens que não estão no disco nem completed
new_queue = []
already_done = completed | existing_serials
for item in faltantes:
    serial = item["serial"]
    if serial not in already_done:
        new_queue.append(item)

print(f"\nNova fila: {len(new_queue)} pending")
print(f"Já done: {len(already_done)}")

# 5. Salvar queue
q["queue"] = new_queue
q["in_progress"] = {}
# Manter failed apenas para os 7 raros conhecidos
rare = {"SLPS-01224", "SLPS-01259", "SLPS-02366", "SLPM-86880", 
        "SLES-02693", "SLES-01082", "SLPS-02346"}
q["failed"] = {k: v for k, v in failed.items() if k in rare}

json.dump(q, open(os.path.join(STATE, "queue.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\nQueue salva! pending={len(new_queue)} completed={len(completed)} failed={len(q['failed'])}")
