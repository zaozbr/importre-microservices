import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\roms\library\roms\psx')
from _chd_convert_v2 import (
    PSX_DIR, CHD_OUTPUT_DIR, extract_serial, build_chd_name,
    _normalize_stem_for_fuzzy, sanitize_filename, find_cue_for_bin, _base_key
)
from pathlib import Path

# Caso: Blasto (Europe).bin
test_files = [
    "Blasto (Europe).bin",
    "Aqua GT (Europe) (Track 1).bin",
    "Capcom vs. SNK - Millennium Fight 2000 Pro (Europe) (Track 1).bin",
]

chd_files = list(PSX_DIR.glob("*.chd")) + list(CHD_OUTPUT_DIR.glob("*.chd"))
chds = {f.stem.lower() for f in chd_files}
chds = chds | {sanitize_filename(f.stem).lower() for f in chd_files}
chds_norm = {}
for f in chd_files:
    norm = _normalize_stem_for_fuzzy(f.stem).lower()
    if norm:
        chds_norm.setdefault(norm, f.stem)

for name in test_files:
    f = PSX_DIR / name
    if not f.exists():
        # Procurar em duplicados
        f = PSX_DIR / "duplicados" / name
    if not f.exists():
        print(f"NAO EXISTE: {name}")
        continue

    base = f.stem.lower()
    serial = extract_serial(f.name)
    expected_chd = Path(build_chd_name(serial, f.stem)).stem.lower()
    norm = _normalize_stem_for_fuzzy(f.stem).lower()

    print(f"\n=== {name} ===")
    print(f"  Serial: {serial}")
    print(f"  Expected CHD: {expected_chd}")
    print(f"  In chds (exact): {expected_chd in chds}")
    print(f"  Norm: {norm}")
    print(f"  In chds_norm: {norm in chds_norm}")
    if norm in chds_norm:
        print(f"    Matched to: {chds_norm[norm]}")
    # Verificar substring
    matches = [c for c in chds if norm[:20] in c]
    if matches:
        print(f"  Substring matches: {matches[:3]}")
    # Tem CUE?
    cue = find_cue_for_bin(f)
    print(f"  CUE: {cue}")
