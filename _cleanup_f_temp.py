#!/usr/bin/env python3
"""Analisa BINs em F:\chd_temp:
1. Se ja tem CHD em psx/ -> mover para dup
2. Se tem CUE correspondente em dup/ -> mover CUE+BIN para psx/ e converter
3. Se nao tem CUE -> mover para dup
"""
import sys, re, shutil
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

F = Path(r"F:\chd_temp")
PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

def normalize(s):
    s = re.sub(r'\[?[A-Z]{2,4}[-]\d{3,5}\]?', '', s)
    s = re.sub(r'\(Track\s*\d+\)', '', s, flags=re.I)
    s = re.sub(r'\(Disc\s*\d+\)', '', s, flags=re.I)
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()

# CHDs existentes em psx/
chd_serials = set()
chd_norms = set()
for c in PSX.glob("*.chd"):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
    if m: chd_serials.add(m.group(1).upper())
    chd_norms.add(normalize(c.stem))

# CUEs em dup/
dup_cues = list(DUP.glob("*.cue")) if DUP.exists() else []
dup_cue_norms = {}
for c in dup_cues:
    dup_cue_norms[normalize(c.stem)] = c

# BINs em F:
bins = list(F.glob("*.bin"))
cues_f = list(F.glob("*.cue"))

print(f"BINs em F: {len(bins)}")
print(f"CUEs em F: {len(cues_f)}")
print(f"CUEs em dup: {len(dup_cues)}")
print()

to_convert = []  # (bin_path, cue_path)
to_dup = []

for bin_f in bins:
    serial = extract_serial(bin_f.name)
    norm = normalize(bin_f.stem)

    # 1. Ja tem CHD?
    if serial and serial in chd_serials:
        print(f"  [CHD exists] {bin_f.name[:50]:50s} serial={serial}")
        to_dup.append(bin_f)
        continue
    if norm in chd_norms:
        print(f"  [CHD fuzzy]  {bin_f.name[:50]:50s}")
        to_dup.append(bin_f)
        continue

    # 2. Tem CUE em dup?
    if norm in dup_cue_norms:
        cue = dup_cue_norms[norm]
        print(f"  [CUE in dup] {bin_f.name[:50]:50s} -> {cue.name[:40]}")
        to_convert.append((bin_f, cue))
        continue

    # 3. CUE em F:?
    for cue_f in cues_f:
        if normalize(cue_f.stem) == norm or cue_f.stem in bin_f.name:
            print(f"  [CUE in F:]  {bin_f.name[:50]:50s} -> {cue_f.name[:40]}")
            to_convert.append((bin_f, cue_f))
            break
    else:
        # 4. Sem CUE — mover para dup
        print(f"  [NO CUE]     {bin_f.name[:50]:50s} -> dup")
        to_dup.append(bin_f)

print(f"\nPara converter: {len(to_convert)}")
print(f"Para dup: {len(to_dup)}")

# Mover BINs para dup
moved_dup = 0
for f in to_dup:
    dst = DUP / f.name
    try:
        if dst.exists(): dst.unlink()
        shutil.move(str(f), str(dst))
        moved_dup += 1
    except Exception as e:
        print(f"  ERR moving {f.name}: {e}")

# Mover CUEs+BINs para psx/ para conversao
moved_psx = 0
for bin_f, cue_f in to_convert:
    # Mover BIN
    dst_bin = PSX / bin_f.name
    try:
        if dst_bin.exists(): dst_bin.unlink()
        shutil.move(str(bin_f), str(dst_bin))
    except Exception as e:
        print(f"  ERR moving bin {bin_f.name}: {e}")
        continue
    # Mover CUE
    dst_cue = PSX / cue_f.name
    try:
        if dst_cue.exists(): dst_cue.unlink()
        shutil.move(str(cue_f), str(dst_cue))
        moved_psx += 1
    except Exception as e:
        print(f"  ERR moving cue {cue_f.name}: {e}")

print(f"\nMovidos para dup: {moved_dup}")
print(f"Movidos para psx (p/ conversao): {moved_psx}")

# Limpar CUEs temporarios em F: (_cue_*)
for cue_f in cues_f:
    if cue_f.name.startswith("_cue_") or cue_f.name.startswith("_"):
        try: cue_f.unlink()
        except: pass

# Limpar CHDs 0KB em F:
for chd_f in F.glob("*.chd"):
    if chd_f.stat().st_size < 1024:
        try: chd_f.unlink()
        except: pass

# Limpar arquivos _chd_err_*
for err_f in F.glob("_chd_err_*"):
    try: err_f.unlink()
    except: pass

print("Limpeza de F: concluida")
