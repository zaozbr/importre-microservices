import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

src = Path(r"F:\chd_temp")
dst = Path(r"D:\roms\library\roms")

chd_names = set(c.stem.lower() for c in dst.glob("*.chd"))

for f in sorted(src.glob("*.bin")):
    stem = f.stem
    base = re.sub(r'_(\d+)$', '', stem)
    found = False
    for cn in chd_names:
        if base.lower() in cn or cn in base.lower():
            found = True
            break
    status = "CHD existe" if found else "SEM CHD"
    size = f.stat().st_size / 1024 / 1024
    print(f"  {status:>10} | {size:>8.1f}MB | {f.name}")
