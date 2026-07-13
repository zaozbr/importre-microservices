from pathlib import Path
PSX = Path(r"D:\roms\library\roms\psx")
b = PSX / "Simple 1500 Series Vol.70 - The War Simulation - Nin no Tsukurishisha-tachi (Japan).bin"
c = b.with_suffix(".cue")
c.write_text(f'FILE "{b.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n', encoding="utf-8")
print("OK")
