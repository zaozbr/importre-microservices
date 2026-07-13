import subprocess, shutil, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")
F = Path(r"F:\chd_temp")
F.mkdir(exist_ok=True)
DUP = Path(r"D:\roms\duplicados")

cue = PSX / "Alex Ferguson's Player Manager 2002 (Europe) (Track 1).cue"
binf = PSX / "Alex Ferguson's Player Manager 2002 (Europe) (Track 1).bin"

# Copiar para F:
img = F / "afpm2002.bin"
shutil.copy2(str(binf), str(img))
cuef = F / "afpm2002.cue"
cuef.write_text(f'FILE "{img.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n', encoding="utf-8")

chd = F / "Alex-Fergusons-Player-Manager-2002.chd"
r = subprocess.run([str(PSX / "chdman.exe"), "createcd", "-i", str(cuef), "-o", str(chd), "-f"],
                   capture_output=True, text=True, timeout=300)
print("rc=", r.returncode)
if r.stderr: print(r.stderr[:300])

if chd.exists() and chd.stat().st_size > 1024 * 1024:
    # Verify
    v = subprocess.run([str(PSX / "chdman.exe"), "verify", "-i", str(chd)],
                       capture_output=True, text=True, timeout=120)
    print("verify rc=", v.returncode)
    if v.returncode == 0:
        # Mover CHD para psx/
        dst = PSX / chd.name
        shutil.move(str(chd), str(dst))
        print(f"OK: {dst.name} ({dst.stat().st_size//1024}KB)")
        # Mover fonte para dup/
        for f in [cue, binf]:
            d = DUP / f.name
            if d.exists(): d.unlink()
            shutil.move(str(f), str(d))
            print(f"Movido para dup: {f.name}")
    else:
        print(f"VERIFY FALHOU: {v.stderr[:200]}")
        chd.unlink(missing_ok=True)
else:
    print("FALHA: CHD nao criado")

# Limpar temp
img.unlink(missing_ok=True)
cuef.unlink(missing_ok=True)
