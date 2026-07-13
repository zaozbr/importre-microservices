"""Reativa sites adicionais para ampliar busca."""
import json
from pathlib import Path

SITES_PATH = Path(r"D:\roms\library\roms\_importre_state\sites.json")

# Sites para reativar (com prioridade)
ENABLE = {
    "coolrom": 6,
    "vimm": 9,
    "cdromance": 10,
    "romhustler": 12,
    "myrient": 3,
    "romspack": 3,
    "totalroms": 3,
    "romspure": 3,
    "roms2000": 3,
    "classicgames": 3,
    "retrobit": 3,
    "freeroms": 3,
}

with open(SITES_PATH, "r", encoding="utf-8") as f:
    sites = json.load(f)

for key, prio in ENABLE.items():
    if key in sites:
        sites[key]["enabled"] = True
        sites[key]["priority"] = prio
        print(f"Reativado: {key} (priority {prio})")

with open(SITES_PATH, "w", encoding="utf-8") as f:
    json.dump(sites, f, indent=2, ensure_ascii=False)

print("Done")
