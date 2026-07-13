import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

psx = Path(r"D:\roms\library\roms\psx")
dup = psx / "duplicados"

# Indexar CHDs por serial
chd_serials = set()
for c in list(psx.glob("*.chd")) + list(dup.glob("*.chd")) if dup.exists() else []:
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
    if m:
        chd_serials.add(m.group(1).upper())
    chd_serials.add(c.stem.lower())

# CUEs com BIN existente, sem CHD
convertible_main = []
convertible_dup = []

for base, label in [(psx, "main"), (dup, "dup")] if dup.exists() else [(psx, "main")]:
    for cue in base.glob("*.cue"):
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', cue.stem, re.I)
        serial = m.group(1).upper() if m else None
        if serial and serial in chd_serials:
            continue
        if cue.stem.lower() in chd_serials:
            continue
        # Verificar se BIN existe
        content = cue.read_text(encoding="utf-8", errors="replace")
        refs = re.findall(r'FILE\s+"([^"]+)"', content)
        has_bin = False
        for ref in refs:
            bin_path = cue.parent / ref
            if bin_path.exists():
                has_bin = True
                break
            # Fuzzy: sem prefixo
            for prefix in ["psx_", "psx-"]:
                if ref.startswith(prefix):
                    bin_path = cue.parent / ref[len(prefix):]
                    if bin_path.exists():
                        has_bin = True
                        break
            if has_bin:
                break
        if has_bin:
            if label == "main":
                convertible_main.append(cue)
            else:
                convertible_dup.append(cue)

# BINs sem CUE, sem CHD (bin isolado)
bins_isolated_main = []
bins_isolated_dup = []
for base, label in [(psx, "main"), (dup, "dup")] if dup.exists() else [(psx, "main")]:
    for f in base.glob("*"):
        if f.suffix.lower() not in {".bin", ".img", ".iso"}:
            continue
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', f.stem, re.I)
        serial = m.group(1).upper() if m else None
        if serial and serial in chd_serials:
            continue
        if f.stem.lower() in chd_serials:
            continue
        # Tem CUE?
        cue = f.with_suffix(".cue")
        if cue.exists():
            continue  # ja contado acima
        # Pular multi-track (so Track 1)
        if re.search(r'Track\s*[2-9]', f.stem, re.I):
            continue
        if label == "main":
            bins_isolated_main.append(f)
        else:
            bins_isolated_dup.append(f)

print(f"=== ROMs PSX convertiveis ===")
print(f"  CUEs com BIN (main):     {len(convertible_main)}")
print(f"  CUEs com BIN (dup):      {len(convertible_dup)}")
print(f"  BINs sem CUE (main):     {len(bins_isolated_main)}")
print(f"  BINs sem CUE (dup):      {len(bins_isolated_dup)}")
print(f"  TOTAL convertiveis:      {len(convertible_main)+len(convertible_dup)+len(bins_isolated_main)+len(bins_isolated_dup)}")
print()
print(f"  CUEs sem BIN (main):     {sum(1 for c in psx.glob('*.cue') if c not in convertible_main)}")
