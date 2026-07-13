#!/usr/bin/env python3
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")

targets = [
    "King-of-Fighters-Kyo-SLPM-86095.bin",
    "Simple 1500 Series Hello Kitty Vol.01 - Hello Kitty Bowling (Japan).bin",
    "Simple 1500 Series Vol.70 - The War Simulation - Nin no Tsukurishisha (Japan).bin",
]

for name in targets:
    bin_path = PSX / name
    if not bin_path.exists():
        print(f"NAO ENCONTRADO: {name}")
        continue
    cue_path = bin_path.with_suffix(".cue")
    cue_content = f'FILE "{bin_path.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
    cue_path.write_text(cue_content, encoding="utf-8")
    print(f"OK: {name[:60]}")
