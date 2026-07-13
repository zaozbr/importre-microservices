#!/usr/bin/env python3
"""Para cada CUE sem BIN: busca BIN em subpastas de psx/ e em D:\roms\duplicados.
Se encontrar, copia para junto do CUE. Se nao, move o CUE para D:\roms\duplicados."""
import sys, re, shutil
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# CHDs
chd_serials = set()
for c in PSX.rglob("*.chd"):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
    if m: chd_serials.add(m.group(1).upper())

# Indexar todos os BINs em psx/ (rglob) e dup/
all_bins = {}  # name_lower -> path
for base in [PSX, DUP]:
    if not base.exists(): continue
    for f in base.rglob("*.bin"):
        all_bins[f.name.lower()] = f

# Encontrar CUEs sem BIN
cues_sem_bin = []
for cue in PSX.rglob("*.cue"):
    if "nao-conversivel" in cue.name.lower(): continue
    serial = extract_serial(cue.stem)
    if serial and serial in chd_serials: continue
    try: content = cue.read_text(encoding="utf-8", errors="replace")
    except: continue
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    if not refs: continue
    has_bin = any((cue.parent / r).exists() for r in refs)
    if not has_bin:
        cues_sem_bin.append((cue, serial, refs))

print(f"CUEs sem BIN: {len(cues_sem_bin)}")

found = 0
moved = 0
for cue, serial, refs in cues_sem_bin:
    # Tentar encontrar os BINs referenciados em subpastas ou dup
    all_found = True
    for ref in refs:
        ref_name = Path(ref).name.lower()
        if ref_name in all_bins:
            # Copiar BIN para junto do CUE
            src = all_bins[ref_name]
            dst = cue.parent / Path(ref).name
            if not dst.exists():
                try:
                    shutil.copy2(str(src), str(dst))
                    print(f"  [FOUND] {Path(ref).name[:50]} <- {src.parent.name}")
                except Exception as e:
                    print(f"  [ERR] {Path(ref).name[:50]}: {e}")
                    all_found = False
            else:
                print(f"  [EXISTS] {Path(ref).name[:50]}")
        else:
            # Buscar fuzzy pelo stem (sem Track)
            base_stem = re.sub(r'\s*\(Track\s*\d+\)\s*', '', Path(ref).stem, flags=re.I)
            fuzzy_match = None
            for bn, bp in all_bins.items():
                bp_stem = re.sub(r'\s*\(Track\s*\d+\)\s*', '', Path(bn).stem, flags=re.I)
                if bp_stem.lower() == base_stem.lower():
                    fuzzy_match = bp
                    break
            if fuzzy_match:
                dst = cue.parent / Path(ref).name
                if not dst.exists():
                    try:
                        shutil.copy2(str(fuzzy_match), str(dst))
                        print(f"  [FUZZY] {Path(ref).name[:50]} <- {fuzzy_match.parent.name}")
                    except Exception as e:
                        all_found = False
            else:
                all_found = False

    if all_found:
        found += 1
        print(f"  -> RESOLVIDO: {cue.name[:50]}")
    else:
        # Mover CUE para dup
        dst = DUP / cue.name
        if dst.exists():
            cue.unlink()
        else:
            try: shutil.move(str(cue), str(dst))
            except: pass
        moved += 1
        print(f"  -> MOVIDO para dup: {cue.name[:50]}")

print(f"\nResolvidos (BIN encontrado): {found}")
print(f"Movidos para dup: {moved}")
