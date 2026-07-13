#!/usr/bin/env python3
"""Lista todos os CUEs sem BIN em psx/ (rglob, inclui subpastas)."""
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

for cue in PSX.rglob("*.cue"):
    serial = extract_serial(cue.stem)
    if serial and serial in chd_serials:
        continue
    try:
        content = cue.read_text(encoding="utf-8", errors="replace")
    except:
        continue
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    if not refs:
        continue
    has_bin = any((cue.parent / r).exists() for r in refs)
    if not has_bin:
        size = cue.stat().st_size
        print(f"  {cue.name[:65]:65s} {str(cue.parent)[-30:]:30s} serial={serial}")
