#!/usr/bin/env python3
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")

# Simple 1500 Vol.073 - 2 tracks
t1 = PSX / "Simple 1500 Series Vol.073 - The Invader - Space Invaders 1500 (Japan) (Track 1).bin"
t2 = PSX / "Simple 1500 Series Vol.073 - The Invader - Space Invaders 1500 (Japan) (Track 2).bin"

cue_name = "Simple 1500 Series Vol.073 - The Invader - Space Invaders 1500 (Japan).cue"
cue_path = PSX / cue_name

cue_content = f'FILE "{t1.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\nFILE "{t2.name}" BINARY\n  TRACK 02 AUDIO\n    INDEX 00 00:00:00\n    INDEX 01 00:02:00\n'

cue_path.write_text(cue_content, encoding="utf-8")
print(f"CUE multi-track gerado: {cue_name}")
