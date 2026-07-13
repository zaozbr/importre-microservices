import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

dup = Path(r"D:\roms\duplicados")
for name in ["Pi to Mail-SLPS-01866.bin", "Shin DX Okumanchouja Game(Track 1)-SLPM-87251.bin", "SD Gundam - GCentury(Track 01)-SLPS-00785.bin"]:
    p = dup / name
    status = "EXISTS" if p.exists() else "NOT FOUND"
    print(f"  {status:>10} | {name}")
    if not p.exists():
        stem = Path(name).stem
        matches = list(dup.glob(f"{stem[:20]}*"))
        for m in matches[:3]:
            print(f"    SIMILAR: {m.name}")
