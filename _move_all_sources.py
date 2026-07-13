#!/usr/bin/env python3
"""Move TODAS as fontes (CUE+BIN, BIN sem CUE, ISO, IMG, MDF, ECM) que ja tem CHD correspondente para D:\roms\duplicados."""
import sys, re, shutil
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")
DUP.mkdir(exist_ok=True)

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

moved = 0
skipped = 0

# CUEs
for cue in PSX.rglob("*.cue"):
    if "nao-conversivel" in cue.name.lower(): continue
    serial = extract_serial(cue.stem)
    norm = normalize(cue.stem)
    has_chd = (serial and serial in chd_serials) or (norm in chd_norms)
    if not has_chd: continue
    # Mover CUE
    dst = DUP / cue.name
    if not dst.exists():
        try: shutil.move(str(cue), str(dst)); moved += 1
        except: pass
    else:
        try: cue.unlink(); moved += 1
        except: pass
    # Mover BINs referenciados
    try:
        content = cue.read_text(encoding="utf-8", errors="replace") if cue.exists() else ""
    except: content = ""
    # Ler do destino se ja movido
    if not content and dst.exists():
        try: content = dst.read_text(encoding="utf-8", errors="replace")
        except: content = ""
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    for ref in refs:
        binf = PSX / cue.parent.name / ref if cue.parent != PSX else PSX / ref
        if not binf.exists():
            binf = cue.parent / ref if cue.parent.exists() else None
        if binf and binf.exists():
            d = DUP / binf.name
            if not d.exists():
                try: shutil.move(str(binf), str(d))
                except: pass
            else:
                try: binf.unlink()
                except: pass

# BINs sem CUE
for binf in PSX.rglob("*.bin"):
    if "nao-conversivel" in binf.name.lower(): continue
    serial = extract_serial(binf.stem)
    norm = normalize(binf.stem)
    has_chd = (serial and serial in chd_serials) or (norm in chd_norms)
    if not has_chd: continue
    dst = DUP / binf.name
    if not dst.exists():
        try: shutil.move(str(binf), str(dst)); moved += 1
        except: pass
    else:
        try: binf.unlink(); moved += 1
        except: pass

# ISOs, IMGs, MDFs
for ext in ["*.iso", "*.img", "*.mdf"]:
    for f in PSX.rglob(ext):
        if "nao-conversivel" in f.name.lower(): continue
        serial = extract_serial(f.stem)
        norm = normalize(f.stem)
        has_chd = (serial and serial in chd_serials) or (norm in chd_norms)
        if not has_chd: continue
        dst = DUP / f.name
        if not dst.exists():
            try: shutil.move(str(f), str(dst)); moved += 1
            except: pass
        else:
            try: f.unlink(); moved += 1
            except: pass

# ECMs
for f in PSX.rglob("*.ecm"):
    serial = extract_serial(f.stem)
    norm = normalize(f.stem)
    has_chd = (serial and serial in chd_serials) or (norm in chd_norms)
    if not has_chd: continue
    dst = DUP / f.name
    if not dst.exists():
        try: shutil.move(str(f), str(dst)); moved += 1
        except: pass
    else:
        try: f.unlink(); moved += 1
        except: pass

# CCDs (CloneCD)
for f in PSX.rglob("*.ccd"):
    serial = extract_serial(f.stem)
    norm = normalize(f.stem)
    has_chd = (serial and serial in chd_serials) or (norm in chd_norms)
    if not has_chd: continue
    for ext in [".ccd", ".img", ".sub"]:
        src = f.with_suffix(ext)
        if src.exists():
            dst = DUP / src.name
            if not dst.exists():
                try: shutil.move(str(src), str(dst)); moved += 1
                except: pass
            else:
                try: src.unlink()
                except: pass

# SUBs
for f in PSX.rglob("*.sub"):
    serial = extract_serial(f.stem)
    norm = normalize(f.stem)
    has_chd = (serial and serial in chd_serials) or (norm in chd_norms)
    if not has_chd: continue
    dst = DUP / f.name
    if not dst.exists():
        try: shutil.move(str(f), str(dst)); moved += 1
        except: pass
    else:
        try: f.unlink(); moved += 1
        except: pass

print(f"Fontes movidas para duplicados: {moved}")
