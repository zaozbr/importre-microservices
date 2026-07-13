"""Move arquivos ROM com defeito (sem CHD correspondente) para duplicados/
e reinsere os itens na fila do importre.

Isso resolve o problema do importre considerar itens como 'ja na colecao'
porque existem arquivos .cue/.bin quebrados na pasta principal."""
import json
import re
import shutil
from pathlib import Path
import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _chd_convert_v2 import build_chd_name, extract_serial

PSX_DIR = Path(r"D:\roms\library\roms\psx")
DUP_DIR = PSX_DIR / "duplicados"
CHD_OUTPUT_DIR = Path(r"F:\chd_temp")
QUEUE_PATH = Path(r"D:\roms\library\roms\_importre_state\queue.json")

DUP_DIR.mkdir(exist_ok=True)

# Carregar CHDs existentes
chd_set = {f.name.lower() for f in (list(PSX_DIR.glob("*.chd")) + list(CHD_OUTPUT_DIR.glob("*.chd")))}

# Carregar fila
queue_data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
queue = queue_data.get("queue", [])
in_progress = queue_data.get("in_progress", {})
completed = queue_data.get("completed", {})
failed = queue_data.get("failed", {})

# Conjuntos para nao adicionar duplicado
all_serials = {item.get("serial") for item in queue if item.get("serial")}
all_serials |= set(in_progress.keys())
all_serials |= set(completed.keys())
all_serials |= set(failed.keys())

all_rom_exts = {".cue", ".bin", ".iso", ".img", ".mdf", ".ecm"}

# Identificar grupos de arquivos a mover (mantem todos os tracks juntos)
groups = {}  # key -> list[Path]
for f in PSX_DIR.iterdir():
    if not f.is_file() or f.suffix.lower() not in all_rom_exts:
        continue
    serial = extract_serial(f.name)
    name = re.sub(r"\(Track \d+\)", "", f.stem, flags=re.I).strip()
    expected = build_chd_name(serial, name).lower()
    if expected in chd_set:
        continue
    key = serial if serial else re.sub(r"[^\w\s]", "", name).strip().lower()[:40]
    groups.setdefault(key, []).append(f)

moved = 0
added = 0
moved_files = []
for key, files in groups.items():
    # Determinar serial e nome
    serial = None
    name = None
    for f in files:
        s = extract_serial(f.name)
        if s:
            serial = s
            break
    for f in files:
        n = re.sub(r"\(Track \d+\)", "", f.stem, flags=re.I).strip()
        if n:
            name = n
            break
    if not name:
        name = files[0].stem
    
    # Mover arquivos para duplicados/
    for f in files:
        dest = DUP_DIR / f.name
        if dest.exists():
            dest.unlink()
        shutil.move(str(f), str(dest))
        moved_files.append(f.name)
        moved += 1
    
    # Adicionar a fila se nao existir
    if serial and serial in all_serials:
        continue
    if not serial:
        norm = re.sub(r"[^\w\s]", "", name).strip().lower()[:40]
        found = False
        for item in queue + list(in_progress.values()) + list(completed.values()) + list(failed.values()):
            item_name = re.sub(r"[^\w\s]", "", item.get("name", "")).strip().lower()[:40]
            if item_name == norm:
                found = True
                break
        if found:
            continue
    
    region = "JP"
    if serial:
        if serial.startswith("SLUS") or serial.startswith("SCUS"):
            region = "US"
        elif serial.startswith("SLES") or serial.startswith("SCES") or serial.startswith("SCED"):
            region = "EU"
        elif serial.startswith("SLPS") or serial.startswith("SLPM") or serial.startswith("SCPS") or serial.startswith("PAPX") or serial.startswith("PCPX") or serial.startswith("SLED"):
            region = "JP"
        elif serial.startswith("HBREW") or serial.startswith("HOMEBREW"):
            region = "HB"
    
    section = "## 🇯🇵 Japão" if region == "JP" else ("## 🇪🇺 Europa" if region == "EU" else ("## 🇺🇸 EUA" if region == "US" else ""))
    
    queue.append({
        "serial": serial,
        "name": name,
        "region": region,
        "section": section,
        "type": "commercial" if not serial or not serial.startswith("HB") else "homebrew",
    })
    added += 1
    if serial:
        all_serials.add(serial)

# Salvar fila
queue_data["queue"] = queue
QUEUE_PATH.write_text(json.dumps(queue_data, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Arquivos movidos para duplicados/: {moved}")
print(f"Itens adicionados a fila: {added}")
print(f"Total na fila: {len(queue)}")
print("\nJogos movidos:")
for key in list(groups.keys())[:50]:
    print(f"  {key}")
if len(groups) > 50:
    print(f"  ... e mais {len(groups) - 50} jogos")
