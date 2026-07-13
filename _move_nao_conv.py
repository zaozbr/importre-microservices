import shutil
from pathlib import Path
PSX = Path(r"D:\roms\library\roms\psx")
moved = 0
for f in PSX.rglob("*nao-conversivel*"):
    if f.parent == PSX:
        continue
    dst = PSX / f.name
    if dst.exists():
        f.unlink()
        moved += 1
    else:
        shutil.move(str(f), str(dst))
        moved += 1
print(f"Movidos para raiz psx/: {moved}")
