"""Prepara lista de downloads pendentes e realimenta a fila do importre."""
import json
import re
from pathlib import Path
import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _chd_convert_v2 import build_chd_name, extract_serial

PSX_DIR = Path(r"D:\roms\library\roms\psx")
CHD_OUTPUT_DIR = Path(r"F:\chd_temp")
QUEUE_PATH = Path(r"D:\roms\library\roms\_importre_state\queue.json")

# Carregar fila
queue_data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
queue = queue_data.get("queue", [])
in_progress = queue_data.get("in_progress", {})
completed = queue_data.get("completed", {})
queue_serials = {item.get("serial") for item in queue if item.get("serial")}
queue_serials |= set(in_progress.keys())
queue_serials |= set(completed.keys())

# Carregar CHDs
chd_set = {f.name.lower() for f in (list(PSX_DIR.glob("*.chd")) + list(CHD_OUTPUT_DIR.glob("*.chd")))}

# ROMs sem CHD
all_rom_exts = {".cue", ".bin", ".iso", ".img", ".mdf", ".ecm"}
rom_files = [f for f in PSX_DIR.iterdir() if f.is_file() and f.suffix.lower() in all_rom_exts]

missing_games = {}  # serial -> {name, files, region}
for f in rom_files:
    serial = extract_serial(f.name)
    name = re.sub(r"\(Track \d+\)", "", f.stem, flags=re.I).strip()
    expected = build_chd_name(serial, name).lower()
    if expected in chd_set:
        continue
    
    # Agrupar por serial ou nome base
    key = serial if serial else re.sub(r"[^\w\s]", "", name).strip().lower()[:40]
    region = "JP" if serial and (serial.startswith("SLPS") or serial.startswith("SLPM") or serial.startswith("SCPS") or serial.startswith("PAPX") or serial.startswith("PCPX") or serial.startswith("SLED")) else ("EU" if serial and serial.startswith("SLES") else ("US" if serial and serial.startswith("SLUS") else "JP"))
    
    if key not in missing_games:
        missing_games[key] = {
            "serial": serial,
            "name": name,
            "region": region,
            "files": [],
            "section": "## 🇯🇵 Japão" if region == "JP" else ("## 🇪🇺 Europa" if region == "EU" else "## 🇺🇸 EUA"),
        }
    missing_games[key]["files"].append(f.name)

# Adicionar itens de _chd_failed que nao estao em missing_games
failed_dir = PSX_DIR / "_chd_failed"
if failed_dir.exists():
    for f in failed_dir.iterdir():
        if not f.is_file() or f.suffix.lower() not in {".bin", ".cue", ".iso", ".img", ".mdf", ".ecm"}:
            continue
        serial = extract_serial(f.name)
        if serial and serial in queue_serials:
            continue
        name = re.sub(r"\(Track \d+\)", "", f.stem, flags=re.I).strip()
        key = serial if serial else re.sub(r"[^\w\s]", "", name).strip().lower()[:40]
        if key in missing_games:
            continue
        region = "JP" if serial and (serial.startswith("SLPS") or serial.startswith("SLPM") or serial.startswith("SCPS") or serial.startswith("PAPX") or serial.startswith("PCPX") or serial.startswith("SLED")) else ("EU" if serial and serial.startswith("SLES") else ("US" if serial and serial.startswith("SLUS") else "JP"))
        missing_games[key] = {
            "serial": serial,
            "name": name,
            "region": region,
            "files": [f.name],
            "section": "## 🇯🇵 Japão" if region == "JP" else ("## 🇪🇺 Europa" if region == "EU" else "## 🇺🇸 EUA"),
        }

# Preparar lista
items_to_add = []
for key, game in missing_games.items():
    serial = game["serial"]
    if serial and serial in queue_serials:
        print(f"[JA NA FILA] {serial} - {game['name']}")
        continue
    items_to_add.append(game)

print(f"\n{'='*60}")
print(f"ITENS PARA ADICIONAR A FILA: {len(items_to_add)}")
print(f"{'='*60}")
for game in items_to_add:
    serial = game["serial"]
    print(f"  {serial or 'N/A':15s} [{game['region']}] {game['name']}")
    for fname in game["files"]:
        print(f"    - {fname}")

# Confirmar e adicionar
print(f"\nAdicionando {len(items_to_add)} itens a fila do importre...")
queue_data.setdefault("completed", {})
queue_data.setdefault("failed", {})
queue_data.setdefault("retry_count", {})

added = 0
for game in items_to_add:
    serial = game["serial"]
    # Limpar de completed/failed/retry_count
    for section in ["completed", "failed", "retry_count"]:
        if serial and serial in queue_data[section]:
            del queue_data[section][serial]
    
    queue.append({
        "serial": serial,
        "name": game["name"],
        "region": game["region"],
        "section": game["section"],
        "type": "commercial",
    })
    added += 1

queue_data["queue"] = queue
QUEUE_PATH.write_text(json.dumps(queue_data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Adicionados: {added}")
print(f"Tamanho total da fila: {len(queue)}")
