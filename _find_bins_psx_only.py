#!/usr/bin/env python3
import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

chd_serials = set()
for c in PSX.rglob("*.chd"):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
    if m: chd_serials.add(m.group(1).upper())

cue_referenced_bins = set()
for cue in PSX.rglob("*.cue"):
    try:
        content = cue.read_text(encoding="utf-8", errors="replace")
        refs = re.findall(r'FILE\s+"([^"]+)"', content)
        for ref in refs:
            cue_referenced_bins.add(Path(ref).name.lower())
    except: pass

for f in PSX.rglob("*.bin"):
    serial = extract_serial(f.stem)
    if serial and serial in chd_serials: continue
    if f.with_suffix(".cue").exists(): continue
    if f.name.lower() in cue_referenced_bins: continue
    size_mb = f.stat().st_size / (1024*1024)
    print(f"{f.name[:70]:70s} {size_mb:8.1f}MB  {f.parent}")
