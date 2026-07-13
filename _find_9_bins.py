#!/usr/bin/env python3
"""Encontra os 9 BINs realmente sem CUE e sem serem referenciados por nenhum CUE."""
import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# CHDs
chd_serials = set()
chd_stems = set()
for base in [PSX, DUP]:
    if not base.exists(): continue
    for c in base.rglob("*.chd"):
        chd_stems.add(c.stem.lower())
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
        if m: chd_serials.add(m.group(1).upper())

# BINs referenciados por CUEs
cue_referenced_bins = set()
for base in [PSX, DUP]:
    if not base.exists(): continue
    for cue in base.rglob("*.cue"):
        try:
            content = cue.read_text(encoding="utf-8", errors="replace")
            refs = re.findall(r'FILE\s+"([^"]+)"', content)
            for ref in refs:
                cue_referenced_bins.add(Path(ref).name.lower())
        except: pass

# Encontrar BINs sem CUE e sem referencia
for base, label in [(PSX, "psx"), (DUP, "dup")]:
    if not base.exists(): continue
    for f in base.rglob("*.bin"):
        serial = extract_serial(f.stem)
        if serial and serial in chd_serials: continue
        if f.stem.lower() in chd_stems: continue
        if f.with_suffix(".cue").exists(): continue
        if f.name.lower() in cue_referenced_bins: continue
        size_mb = f.stat().st_size / (1024*1024)
        print(f"{label:4s} {f.name[:70]:70s} {size_mb:8.1f}MB  {f.parent}")
