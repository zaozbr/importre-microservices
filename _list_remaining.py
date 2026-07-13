#!/usr/bin/env python3
"""Lista fontes em psx/ que ja tem CHD mas nao foram movidas."""
import sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")

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

chd_serials = set()
chd_norms = set()
for c in PSX.glob("*.chd"):
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", c.stem, re.I)
    if m: chd_serials.add(m.group(1).upper())
    chd_norms.add(normalize(c.stem))

remaining = []
for ext in ["*.cue", "*.bin", "*.iso", "*.img", "*.mdf", "*.ecm", "*.ccd", "*.sub"]:
    for f in PSX.rglob(ext):
        if "nao-conversivel" in f.name.lower(): continue
        serial = extract_serial(f.stem)
        norm = normalize(f.stem)
        has_chd = (serial and serial in chd_serials) or (norm in chd_norms)
        if has_chd:
            remaining.append(f)

print(f"Fontes com CHD ainda em psx/: {len(remaining)}")
for f in remaining:
    serial = extract_serial(f.stem)
    print(f"  {serial or '':12s} {f.suffix:5s} {f.relative_to(PSX)}")
