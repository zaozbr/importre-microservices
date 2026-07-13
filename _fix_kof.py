from pathlib import Path
PSX = Path(r"D:\roms\library\roms\psx")
b = PSX / "King-of-Fighters-Kyo-SLPM-86095.bin"
c = b.with_suffix(".cue")
c.write_text(f'FILE "{b.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n', encoding="utf-8")
print(f"OK: {c.name} criado, existe={c.exists()}")
