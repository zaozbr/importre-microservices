#!/usr/bin/env python3
import shutil
from pathlib import Path
PSX = Path(r"D:\roms\library\roms\psx")
src = PSX / "Baby Universe (SCPS-18006)" / "cd image" / "BABY_UNIVERSE.BIN"
dst = PSX / "BABY_UNIVERSE.BIN"
shutil.move(str(src), str(dst))
cue = dst.with_suffix(".cue")
cue.write_text(f'FILE "{dst.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n', encoding="utf-8")
print("OK - movido e CUE gerado")
# Limpar subpastas vazias
for d in [PSX / "Baby Universe (SCPS-18006)" / "cd image", PSX / "Baby Universe (SCPS-18006)"]:
    try:
        if d.exists() and not any(d.iterdir()):
            d.rmdir()
            print(f"Pasta vazia removida: {d.name}")
    except Exception as e:
        print(f"Nao pode remover {d.name}: {e}")
