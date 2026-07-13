import shutil, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")
DUP.mkdir(exist_ok=True)

# Redump: Zero Divide 2
redump = PSX / "Redump"
if redump.exists():
    for f in redump.iterdir():
        dst = DUP / f.name
        if dst.exists(): dst.unlink()
        shutil.move(str(f), str(dst))
    redump.rmdir()
    print(f"Redump: {len(list(DUP.glob('Zero_Divide_2*')))} arquivos movidos para dup, pasta removida")

# Millennium Soldier - Expendable (German)
mill = PSX / "Millennium Soldier - Expendable (PSX) (German)"
if mill.exists():
    cd = mill / "CD"
    if cd.exists():
        for f in cd.iterdir():
            dst = DUP / f.name
            if dst.exists(): dst.unlink()
            shutil.move(str(f), str(dst))
        cd.rmdir()
    mill.rmdir()
    print("Millennium Soldier: arquivos movidos para dup, pasta removida")
