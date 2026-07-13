#!/usr/bin/env python3
"""Para cada CUE sem BIN em psx/: busca BIN em D:\roms\duplicados.
Se encontrar, copia para junto do CUE. Se nao, move o CUE para duplicados."""
import sys, re, shutil
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", name, re.I)
    return m.group(1).upper() if m else None

# Indexar todos os BINs em dup/ por nome
dup_bins = {}
if DUP.exists():
    for f in DUP.rglob("*.bin"):
        dup_bins[f.name.lower()] = f
    # Tambem indexar por stem normalizado (sem Track)
    for f in DUP.rglob("*.bin"):
        stem = re.sub(r'\s*\(Track\s*\d+\)\s*', '', f.stem, flags=re.I)
        dup_bins.setdefault(stem.lower(), f)

# CHDs existentes para pular CUEs que ja tem CHD
chd_serials = set()
chd_norms = set()
for c in PSX.glob("*.chd"):
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", c.stem, re.I)
    if m: chd_serials.add(m.group(1).upper())
    def norm(s):
        s = re.sub(r'\[?[A-Z]{2,4}[-]\d{3,5}\]?', '', s)
        s = re.sub(r'\(Track\s*\d+\)', '', s, flags=re.I)
        s = re.sub(r'\(Disc\s*\d+\)', '', s, flags=re.I)
        s = re.sub(r'\(.*?\)', '', s)
        s = re.sub(r'[^\w\s]', '', s)
        s = re.sub(r'\s+', ' ', s)
        return s.strip().lower()
    chd_norms.add(norm(c.stem))

found = 0
moved = 0
no_bin = 0

for cue in list(PSX.rglob("*.cue")):
    if "nao-conversivel" in cue.name.lower():
        continue
    serial = extract_serial(cue.stem)
    # Pular se ja tem CHD
    def norm(s):
        s = re.sub(r'\[?[A-Z]{2,4}[-]\d{3,5}\]?', '', s)
        s = re.sub(r'\(Track\s*\d+\)', '', s, flags=re.I)
        s = re.sub(r'\(Disc\s*\d+\)', '', s, flags=re.I)
        s = re.sub(r'\(.*?\)', '', s)
        s = re.sub(r'[^\w\s]', '', s)
        s = re.sub(r'\s+', ' ', s)
        return s.strip().lower()
    if serial and serial in chd_serials:
        continue
    if norm(cue.stem) in chd_norms:
        continue

    try:
        content = cue.read_text(encoding="utf-8", errors="replace")
    except:
        continue
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    if not refs:
        continue
    has_bin = all((cue.parent / r).exists() for r in refs)
    if has_bin:
        continue  # ja tem BIN

    # Buscar BINs em dup/
    all_found = True
    for ref in refs:
        ref_name = Path(ref).name
        ref_lower = ref_name.lower()
        dst = cue.parent / ref_name

        if dst.exists():
            continue

        # Match exato por nome
        if ref_lower in dup_bins:
            src = dup_bins[ref_lower]
            try:
                shutil.copy2(str(src), str(dst))
                print(f"  [FOUND] {ref_name[:50]:50s} <- {src.parent.name}")
            except Exception as e:
                print(f"  [ERR] {ref_name[:50]}: {e}")
                all_found = False
        else:
            # Match fuzzy por stem (sem Track)
            base_stem = re.sub(r'\s*\(Track\s*\d+\)\s*', '', Path(ref).stem, flags=re.I)
            fuzzy_key = base_stem.lower()
            if fuzzy_key in dup_bins:
                src = dup_bins[fuzzy_key]
                try:
                    shutil.copy2(str(src), str(dst))
                    print(f"  [FUZZY] {ref_name[:50]:50s} <- {src.parent.name}")
                except Exception as e:
                    all_found = False
            else:
                # Tentar match por nome parcial
                partial_match = None
                for bn, bp in dup_bins.items():
                    if base_stem.lower() in bn or bn in base_stem.lower():
                        partial_match = bp
                        break
                if partial_match:
                    try:
                        shutil.copy2(str(partial_match), str(dst))
                        print(f"  [PARTIAL] {ref_name[:50]:50s} <- {partial_match.parent.name}")
                    except:
                        all_found = False
                else:
                    print(f"  [NOT FOUND] {ref_name[:50]:50s}")
                    all_found = False

    if all_found:
        found += 1
        print(f"  -> RESOLVIDO: {cue.relative_to(PSX)}")
    else:
        # Mover CUE para dup
        dst_cue = DUP / cue.name
        if not dst_cue.exists():
            try:
                shutil.move(str(cue), str(dst_cue))
                moved += 1
                print(f"  -> MOVIDO para dup: {cue.name[:50]}")
            except:
                pass
        else:
            try:
                cue.unlink()
                moved += 1
            except:
                pass

print(f"\n=== RESUMO ===")
print(f"Resolvidos (BIN encontrado em dup): {found}")
print(f"Movidos para dup (sem BIN):         {moved}")
