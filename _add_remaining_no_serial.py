#!/usr/bin/env python3
"""Verifica quais dos 78 itens sem serial da web ainda nao estao na fila e adiciona."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")

# Carregar lista original
orig = json.loads((PSX / "_cues_sem_serial.json").read_text(encoding="utf-8"))
sem_serial = orig["sem_serial"]

# Carregar seriais encontrados
found = {}
for i in range(4):
    f = PSX / f"_serials_found_{i}.json"
    if f.exists():
        for item in json.loads(f.read_text(encoding="utf-8")):
            if item.get("serial"):
                found[item["cue"]] = item["serial"]

# Itens que continuam sem serial mesmo apos busca web
still_no_serial = [item for item in sem_serial if item["cue"] not in found]
print(f"Itens ainda sem serial apos busca web: {len(still_no_serial)}")
for item in still_no_serial[:10]:
    print(f"  {item['clean'][:60]}")

# Verificar fila atual
sys.path.insert(0, str(PSX))
from importre import file_lock, file_unlock, load_json, save_json, QUEUE_PATH
fl = file_lock()
try:
    data = load_json(QUEUE_PATH, {})
    q = data.get("queue", [])
    existing_serials = set()
    existing_names = set()
    for item in q:
        if item.get("serial"):
            existing_serials.add(item["serial"].upper())
        if item.get("name"):
            existing_names.add(item["name"].lower().strip())
    for k in data.get("in_progress", {}).keys(): existing_serials.add(k.upper())
    for k in data.get("completed", {}).keys(): existing_serials.add(k.upper())
    for k in data.get("failed", {}).keys(): existing_serials.add(k.upper())

    # Verificar quais dos still_no_serial ja estao na fila por nome
    already_in_queue = 0
    to_add = []
    for item in still_no_serial:
        name = item["stem"]
        if name.lower().strip() in existing_names:
            already_in_queue += 1
        else:
            to_add.append(item)

    print(f"\nJa na fila por nome: {already_in_queue}")
    print(f"Faltam adicionar: {len(to_add)}")

    # Adicionar os que faltam
    added = 0
    for item in to_add:
        data["queue"].append({
            "serial": "",
            "name": item["stem"],
            "region": "",
            "section": "",
            "type": "commercial",
            "_needs_search": True,
            "_no_serial": True,
            "_search_by_name": True,
        })
        existing_names.add(item["stem"].lower().strip())
        added += 1

    data["total"] = len(data.get("queue",[])) + len(data.get("in_progress",{})) + len(data.get("completed",{})) + len(data.get("failed",{}))
    save_json(QUEUE_PATH, data)
    print(f"\nAdicionados sem serial: {added}")
    print(f"Fila total agora: {len(data['queue'])}")
finally:
    file_unlock(fl)
