#!/usr/bin/env python3
"""Remove TODAS as fontes em psx/ que ja tem CHD correspondente.
Se o arquivo ja existe em duplicados, deleta em psx/. Se nao, move para duplicados."""
import sys, re, shutil
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", name, re.I)
    return m.group(1).upper() if m else None

def normalize(s):
    s = re.sub(r'\[?[A-Z]{2,4}[-]\d{3,5}\]?', '', s)
    s = re.sub(r'\(Track\s*\d+\)', '', s, flags=re.I)
    s = re.sub(r'\(Disc\s*\d+\)', '', s, flags=re.I)
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()

# CHDs existentes
chd_serials = set()
chd_norms = set()
for c in PSX.glob("*.chd"):
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", c.stem, re.I)
    if m: chd_serials.add(m.group(1).upper())
    chd_norms.add(normalize(c.stem))

# Indexar duplicados
dup_names = {f.name for f in DUP.iterdir()} if DUP.exists() else set()

removed = 0
moved = 0

for ext in ["*.cue", "*.bin", "*.iso", "*.img", "*.mdf", "*.ecm", "*.ccd", "*.sub"]:
    for f in list(PSX.rglob(ext)):
        if "nao-conversivel" in f.name.lower():
            continue
        serial = extract_serial(f.stem)
        norm = normalize(f.stem)
        has_chd = (serial and serial in chd_serials) or (norm in chd_norms)
        if not has_chd:
            continue
        # Ja existe em dup? Deletar em psx
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
