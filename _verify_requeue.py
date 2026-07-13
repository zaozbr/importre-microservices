"""Verifica se todos os jogos problemáticos estão na fila do importre."""
import json
from pathlib import Path
import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _chd_convert_v2 import build_chd_name, extract_serial

PSX_DIR = Path(r"D:\roms\library\roms\psx")
CHD_OUTPUT_DIR = Path(r"F:\chd_temp")
QUEUE_PATH = Path(r"D:\roms\library\roms\_importre_state\queue.json")

queue_data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
queue_serials = {item.get("serial") for item in queue_data.get("queue", []) if item.get("serial")}
queue_serials |= set(queue_data.get("in_progress", {}).keys())
queue_serials |= set(queue_data.get("completed", {}).keys())

chd_set = {f.name.lower() for f in (list(PSX_DIR.glob("*.chd")) + list(CHD_OUTPUT_DIR.glob("*.chd")))}

all_rom_exts = {".cue", ".bin", ".iso", ".img", ".mdf", ".ecm"}
rom_files = [f for f in PSX_DIR.iterdir() if f.is_file() and f.suffix.lower() in all_rom_exts]

missing = []
for f in rom_files:
    serial = extract_serial(f.name)
    name = f.stem
    import re
    name = re.sub(r"\(Track \d+\)", "", name, flags=re.I).strip()
    expected = build_chd_name(serial, name).lower()
    if expected in chd_set:
        continue
    if serial and serial in queue_serials:
        continue
    if not serial:
        # Verificar por nome
        key = re.sub(r"[^\w\s]", "", name).strip().lower()[:40]
        found = False
        for q in queue_data.get("queue", []) + list(queue_data.get("in_progress", {}).values()) + list(queue_data.get("completed", {}).values()):
            qname = re.sub(r"[^\w\s]", "", q.get("name", "")).strip().lower()[:40]
            if qname == key:
                found = True
                break
        if found:
            continue
    missing.append((f.name, serial or "N/A", name))

# Verificar _chd_failed
failed_dir = PSX_DIR / "_chd_failed"
if failed_dir.exists():
    for f in failed_dir.iterdir():
        if f.is_file() and f.suffix.lower() in all_rom_exts:
            serial = extract_serial(f.name)
            if serial and serial in queue_serials:
                continue
            missing.append((f"_chd_failed/{f.name}", serial or "N/A", f.stem))

print(f"Itens ainda nao na fila: {len(missing)}")
for fname, serial, name in missing:
    print(f"  {serial:15s} {name}")
    print(f"    arquivo: {fname}")
