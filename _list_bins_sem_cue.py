#!/usr/bin/env python3
import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

cue_refs = set()
for base in [PSX, DUP]:
    if not base.exists(): continue
    for cue in base.glob("*.cue"):
        try:
            content = cue.read_text(encoding="utf-8", errors="replace")
            refs = re.findall(r'FILE\s+"([^"]+)"', content)
            for r in refs: cue_refs.add(Path(r).name.lower())
        except: pass

chd_serials = set()
chd_stems = set()
for base in [PSX, DUP]:
    if not base.exists(): continue
    for c in base.glob("*.chd"):
        chd_stems.add(c.stem.lower())
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
        if m: chd_serials.add(m.group(1).upper())

for base, label in [(PSX, "psx"), (DUP, "dup")]:
    if not base.exists(): continue
    for f in base.glob("*.bin"):
        serial = re.search(r'([A-Z]{2,4}[-]\d{3,5})', f.stem, re.I)
        s = serial.group(1).upper() if serial else None
        if s and s in chd_serials: continue
        if f.stem.lower() in chd_stems: continue
        if f.with_suffix(".cue").exists(): continue
        if f.name.lower() in cue_refs: continue
        print(f"{label:4s} {f.name[:65]:65s} {f.stat().st_size/1024/1024:8.1f}MB")
