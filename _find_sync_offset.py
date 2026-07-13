"""Procura sync bytes em arquivos .bin corrompidos."""
from pathlib import Path

failed_dir = Path(r"D:\roms\library\roms\psx\_chd_failed")
SYNC = bytes([0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00])

for f in sorted(failed_dir.glob("*.bin")):
    print(f"\n=== {f.name} ===")
    data = f.read_bytes()
    print(f"  size: {len(data)}")
    # Procurar sync nos primeiros 1MB
    limit = min(len(data), 1024*1024)
    offsets = []
    pos = 0
    while pos < limit:
        idx = data.find(SYNC, pos, limit)
        if idx == -1:
            break
        offsets.append(idx)
        pos = idx + 1
    print(f"  sync offsets (primeiros 1MB): {offsets[:10]}")
    if offsets:
        first = offsets[0]
        print(f"  primeiro sync em: {first} (mod 2352: {first % 2352}, mod 2048: {first % 2048})")
