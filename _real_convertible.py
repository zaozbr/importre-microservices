import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

psx = Path(r"D:\roms\library\roms\psx")
dup = psx / "duplicados"

# Indexar CHDs por serial (igual ao _chd_convert_v2)
chd_files = list(psx.glob("*.chd")) + (list(dup.glob("*.chd")) if dup.exists() else [])
chd_serials = set()
for c in chd_files:
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
    if m:
        chd_serials.add(m.group(1).upper())

print(f"CHDs por serial: {len(chd_serials)}")

# CUEs sem CHD, com BIN existente
convertible = []
no_bin = []
for base in [psx, dup] if dup.exists() else [psx]:
    for cue in base.glob("*.cue"):
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', cue.stem, re.I)
        serial = m.group(1).upper() if m else None
        if serial and serial in chd_serials:
            continue
        content = cue.read_text(encoding="utf-8", errors="replace")
        refs = re.findall(r'FILE\s+"([^"]+)"', content)
        has_bin = False
        for ref in refs:
            bin_path = cue.parent / ref
            if bin_path.exists():
                has_bin = True
                break
        if has_bin:
            convertible.append(cue)
        else:
            no_bin.append(cue)

# BINs sem CUE, sem CHD, sem multi-track
bins_convertible = []
for base in [psx, dup] if dup.exists() else [psx]:
    for f in base.glob("*.bin"):
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', f.stem, re.I)
        serial = m.group(1).upper() if m else None
        if serial and serial in chd_serials:
            continue
        cue = f.with_suffix(".cue")
        if cue.exists():
            continue
        if re.search(r'Track\s*[2-9]', f.stem, re.I):
            continue
        bins_convertible.append(f)

# IMGs sem CUE, sem CHD
imgs_convertible = []
for base in [psx, dup] if dup.exists() else [psx]:
    for f in base.glob("*.img"):
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', f.stem, re.I)
        serial = m.group(1).upper() if m else None
        if serial and serial in chd_serials:
            continue
        cue = f.with_suffix(".cue")
        if cue.exists():
            continue
        imgs_convertible.append(f)

print(f"\n=== ROMs PSX realmente convertiveis ===")
print(f"  CUEs com BIN, sem CHD:  {len(convertible)}")
print(f"  CUEs sem BIN (precisa download): {len(no_bin)}")
print(f"  BINs sem CUE, sem CHD:  {len(bins_convertible)}")
print(f"  IMGs sem CUE, sem CHD:  {len(imgs_convertible)}")
print(f"  TOTAL convertiveis:     {len(convertible)+len(bins_convertible)+len(imgs_convertible)}")

# Mostrar amostras
print(f"\n=== CUEs convertiveis (primeiros 10) ===")
for c in convertible[:10]:
    print(f"  {c.parent.name}/{c.name[:60]}")

print(f"\n=== BINs convertiveis (primeiros 10) ===")
for f in bins_convertible[:10]:
    print(f"  {f.parent.name}/{f.name[:60]} ({f.stat().st_size/1024/1024:.1f}MB)")
