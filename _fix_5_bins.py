#!/usr/bin/env python3
import shutil
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")

targets = [
    PSX / "Simple 1500 Series Vol.073 - The Invader - Space Invaders 1500 (Japan).bin",
    PSX / "_chd_failed" / "Eisei-Meijin-II-SLPM-86014.bin",
    PSX / "_chd_failed" / "King-of-Fighters-Kyo-SLPM-86095.bin",
    PSX / "_chd_failed" / "Tales-of-Eternia-[Disc1of3]-SLPS-03050.bin",
]

for src in targets:
    if not src.exists():
        print(f"NAO ENCONTRADO: {src.name}")
        continue
    dest = PSX / src.name
    if src.parent != PSX:
        shutil.move(str(src), str(dest))
    cue = dest.with_suffix(".cue")
    cue.write_text(f'FILE "{dest.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n', encoding="utf-8")
    print(f"OK: {dest.name[:60]} -> CUE gerado")
