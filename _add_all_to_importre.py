#!/usr/bin/env python3
"""Consolida seriais encontrados pelos subagentes e adiciona todos à fila do importre.
- Itens COM serial encontrado: adiciona com serial
- Itens SEM serial: adiciona só com nome (campo serial vazio)
"""
import sys, re, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")

# Carregar lista original
orig = json.loads((PSX / "_cues_sem_serial.json").read_text(encoding="utf-8"))
sem_serial = orig["sem_serial"]
com_serial = orig["com_serial"]

# Carregar resultados dos 4 batches
found = {}
for i in range(4):
    f = PSX / f"_serials_found_{i}.json"
    if f.exists():
        for item in json.loads(f.read_text(encoding="utf-8")):
            if item.get("serial"):
                found[item["cue"]] = item["serial"]

print(f"Seriais encontrados na web: {len(found)}")
print(f"Sem serial (vai só com nome): {len(sem_serial) - len(found)}")

# Adicionar à fila do importre
try:
    sys.path.insert(0, str(PSX))
    from importre import file_lock, file_unlock, load_json, save_json, QUEUE_PATH
    fl = file_lock()
    try:
        data = load_json(QUEUE_PATH, {})
        existing = set()
        for q in data.get("queue", []):
            existing.add(q.get("serial", "").upper())
        for k in data.get("in_progress", {}).keys(): existing.add(k.upper())
        for k in data.get("completed", {}).keys(): existing.add(k.upper())
        for k in data.get("failed", {}).keys(): existing.add(k.upper())
        # Também indexar por nome para evitar duplicatas sem serial
        existing_names = set()
        for q in data.get("queue", []):
            if q.get("name"):
                existing_names.add(q["name"].lower().strip())

        added_with_serial = 0
        added_without_serial = 0

        # 1. Itens que tinham serial originalmente (já adicionados antes, mas garantir)
        for item in com_serial:
            s = item["serial"]
            if s in existing: continue
            data["queue"].append({
                "serial": s, "name": item["stem"],
                "region": "", "section": "", "type": "commercial",
                "_needs_search": True,
            })
            existing.add(s)
            added_with_serial += 1

        # 2. Itens sem serial que encontramos serial na web
        for item in sem_serial:
            cue_name = item["cue"]
            serial = found.get(cue_name)
            if serial:
                if serial.upper() in existing: continue
                data["queue"].append({
                    "serial": serial.upper(), "name": item["stem"],
                    "region": "", "section": "", "type": "commercial",
                    "_needs_search": True,
                    "_serial_source": "web_lookup",
                })
                existing.add(serial.upper())
                added_with_serial += 1

        # 3. Itens sem serial mesmo — adicionar só com nome
        for item in sem_serial:
            cue_name = item["cue"]
            if cue_name in found: continue  # já adicionado acima
            name = item["stem"]
            if name.lower().strip() in existing_names: continue
            data["queue"].append({
                "serial": "", "name": name,
                "region": "", "section": "", "type": "commercial",
                "_needs_search": True,
                "_no_serial": True,
                "_search_by_name": True,
            })
            existing_names.add(name.lower().strip())
            added_without_serial += 1

        data["total"] = len(data.get("queue",[])) + len(data.get("in_progress",{})) + len(data.get("completed",{})) + len(data.get("failed",{}))
        save_json(QUEUE_PATH, data)
    finally:
        file_unlock(fl)
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()

print(f"\n=== RESUMO ===")
print(f"  Adicionados COM serial:    {added_with_serial}")
print(f"  Adicionados SEM serial:    {added_without_serial}")
print(f"  Total adicionado:          {added_with_serial + added_without_serial}")
