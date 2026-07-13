import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

psx = Path(r"D:\roms\library\roms\psx")
dup = psx / "duplicados"

chds_main = list(psx.glob("*.chd"))
chds_dup = list(dup.glob("*.chd")) if dup.exists() else []
print(f"CHDs: {len(chds_main)} (main) + {len(chds_dup)} (dup) = {len(chds_main)+len(chds_dup)}")

chd_stems = set(c.stem.lower() for c in chds_main + chds_dup)

bins_no_chd = 0
cues_no_chd = 0
ecms = 0

for base in [psx, dup] if dup.exists() else [psx]:
    for f in base.glob("*"):
        if f.suffix.lower() in {".bin", ".img", ".iso", ".mdf"}:
            m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', f.stem, re.I)
            has_chd = False
            if m:
                serial = m.group(1).lower()
                for cs in chd_stems:
                    if serial in cs:
                        has_chd = True
                        break
            if not has_chd:
                bins_no_chd += 1
        elif f.suffix.lower() == ".cue":
            m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', f.stem, re.I)
            has_chd = False
            if m:
                serial = m.group(1).lower()
                for cs in chd_stems:
                    if serial in cs:
                        has_chd = True
                        break
            if not has_chd:
                cues_no_chd += 1
        elif f.suffix.lower() == ".ecm":
            ecms += 1

print(f"BINs sem CHD: {bins_no_chd}")
print(f"CUEs sem CHD: {cues_no_chd}")
print(f"ECMs: {ecms}")
