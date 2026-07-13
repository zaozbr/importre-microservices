from pathlib import Path
import shutil, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

F = Path(r"F:\chd_temp")
PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def safe_move(src, dst):
    for attempt in range(3):
        try:
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
            return True
        except Exception as e:
            print(f"  retry {attempt+1}: {e}")
            time.sleep(2)
    return False

def safe_del(f):
    for attempt in range(3):
        try:
            f.unlink()
            return True
        except Exception as e:
            print(f"  retry del {attempt+1}: {e}")
            time.sleep(2)
    return False

# CHDs
for chd in F.glob("*.chd"):
    sz = chd.stat().st_size
    if sz > 1024 * 1024:
        dst = PSX / chd.name
        if dst.exists():
            safe_del(chd)
            print(f"CHD ja existe em psx, deletado: {chd.name}")
        elif safe_move(chd, dst):
            print(f"CHD movido para psx: {chd.name} ({sz//1024}KB)")
    else:
        if safe_del(chd):
            print(f"CHD 0KB deletado: {chd.name}")

# BINs
for bin_f in F.glob("*.bin"):
    dst = DUP / bin_f.name
    if safe_move(bin_f, dst):
        print(f"BIN movido para dup: {bin_f.name[:50]}")

# CUEs
for cue in F.glob("*.cue"):
    if safe_del(cue):
        print(f"CUE deletado: {cue.name[:50]}")

# Erros
for err in F.glob("_chd_err_*"):
    safe_del(err)

print("Limpeza concluida")
