#!/usr/bin/env python3
"""Remove fontes em psx/ usando a MESMA logica do _convert_all_cues.py (build_chd_name)."""
import sys, re, shutil
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", name, re.I)
    return m.group(1).upper() if m else None

def sanitize(name):
    for c in '<>:"/\\|?*':
        name = name.replace(c, "")
    if len(name) > 180: name = name[:180]
    return name.strip().rstrip(".")

def build_chd_name(cue_path):
    stem = cue_path.stem
    serial = extract_serial(stem)
    base = re.sub(r"\(Track \d+\)", "", stem, flags=re.I).strip()
    base = re.sub(r"\(Disc \d+\)", "", base, flags=re.I).strip()
    base = re.sub(r"\(.*?\)", "", base).strip()
    base = re.sub(r"[^\w\s-]", "", base)
    base = re.sub(r"\s+", "-", base)
    base = re.sub(r"-+", "-", base).strip("-")
    if serial:
        base = f"{base}-{serial}"
    return sanitize(base) + ".chd"

# CHDs existentes por nome exato
existing_chds = {f.name for f in PSX.glob("*.chd")}

# Indexar duplicados
dup_names = {f.name for f in DUP.iterdir()} if DUP.exists() else set()

removed = 0
moved = 0

for ext in ["*.cue", "*.bin", "*.iso", "*.img", "*.mdf", "*.ecm", "*.ccd", "*.sub"]:
    for f in list(PSX.rglob(ext)):
        if "nao-conversivel" in f.name.lower():
            continue
        # Para CUEs, usar build_chd_name
        if f.suffix.lower() == ".cue":
            chd_name = build_chd_name(f)
            if chd_name not in existing_chds:
                continue
        else:
            # Para BINs/etc, tentar match por serial ou nome normalizado
            serial = extract_serial(f.stem)
            has_chd = False
            if serial:
                for chd in existing_chds:
                    if serial in chd:
                        has_chd = True
                        break
            if not has_chd:
                continue
        # Ja existe em dup? Deletar
        if f.name in dup_names:
            try: f.unlink(); removed += 1
            except: pass
        else:
            dst = DUP / f.name
            if dst.exists():
                try: f.unlink(); removed += 1
                except: pass
            else:
                try: shutil.move(str(f), str(dst)); moved += 1
                except: pass

print(f"Deletados (ja existem em dup): {removed}")
print(f"Movidos para dup:              {moved}")
print(f"Total:                         {removed + moved}")
