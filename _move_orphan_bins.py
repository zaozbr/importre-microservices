import shutil, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

# CUEs existentes (stems) para identificar BINs com CUE
cue_stems = {f.stem.lower() for f in PSX.rglob("*.cue")}

# CHDs existentes por serial
chd_serials = set()
for c in PSX.glob("*.chd"):
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", c.stem, re.I)
    if m: chd_serials.add(m.group(1).upper())

dup_names = {f.name for f in DUP.iterdir()} if DUP.exists() else set()

moved = 0
deleted = 0
for f in list(PSX.rglob("*.bin")):
    if "nao-conversivel" in f.name.lower():
        continue
    # Tem CUE correspondente?
    stem = f.stem.lower()
    # Remover (Track N) para comparar
    base = re.sub(r'\s*\(Track\s*\d+\)\s*', '', stem, flags=re.I)
    if base in cue_stems or stem in cue_stems:
        continue  # tem CUE, nao mover
    # Tem CHD por serial?
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", f.name, re.I)
    if m and m.group(1).upper() in chd_serials:
        pass  # tem CHD, mover
    else:
        # Sem serial e sem CUE - mover tambem (orfao)
        pass
    # Mover para dup
    if f.name in dup_names:
        try: f.unlink(); deleted += 1
        except: pass
    else:
        dst = DUP / f.name
        if dst.exists():
            try: f.unlink(); deleted += 1
            except: pass
        else:
            try: shutil.move(str(f), str(dst)); moved += 1
            except: pass

print(f"Movidos para dup: {moved}")
print(f"Deletados (ja em dup): {deleted}")
print(f"Total: {moved + deleted}")
