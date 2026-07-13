"""Lista arquivos ROM em PSX_DIR que ja tem CHD correspondente."""
import os
import re
import sys
from pathlib import Path
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _chd_convert_v2 import build_chd_name, extract_serial

PSX_DIR = Path(r"D:\roms\library\roms\psx")
ROM_EXTS = {".cue", ".bin", ".iso", ".img", ".mdf", ".ecm"}

chd_set = {f.name.lower() for f in PSX_DIR.glob("*.chd")}

with_chd = []
without_chd = []
for f in PSX_DIR.iterdir():
    if f.is_file() and f.suffix.lower() in ROM_EXTS:
        serial = extract_serial(f.name)
        name = re.sub(r"\(Track \d+\)", "", f.stem, flags=re.I).strip()
        expected = build_chd_name(serial, name).lower()
        if expected in chd_set:
            with_chd.append(f.name)
        else:
            without_chd.append(f.name)

print(f"ROMs com CHD correspondente: {len(with_chd)}")
print(f"ROMs sem CHD correspondente: {len(without_chd)}")
for f in with_chd[:20]:
    print(f"  {f}")
if len(with_chd) > 20:
    print(f"  ... e mais {len(with_chd) - 20}")
