import sys, shutil, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

SRC = Path(r"F:\chd_temp")
DST = Path(r"D:\roms\library\roms")

chds = list(SRC.glob("*.chd"))
print(f"CHDs em F:\\chd_temp: {len(chds)}")

moved = 0
skipped = 0
for chd in chds:
    dst = DST / chd.name
    if dst.exists():
        # Ja existe - comparar tamanho
        if dst.stat().st_size == chd.stat().st_size:
            print(f"  SKIP (ja existe): {chd.name} ({chd.stat().st_size/1024/1024:.1f}MB)")
            chd.unlink()  # apagar origem
            skipped += 1
            continue
        else:
            print(f"  OVERWRITE: {chd.name} (orig={dst.stat().st_size/1024/1024:.1f}MB novo={chd.stat().st_size/1024/1024:.1f}MB)")
    try:
        shutil.move(str(chd), str(dst))
        size = dst.stat().st_size / 1024 / 1024
        print(f"  MOVIDO: {chd.name} ({size:.1f}MB)")
        moved += 1
    except Exception as e:
        print(f"  ERRO: {chd.name}: {e}")

# Limpar arquivos temporarios restantes (.cue, .bin, etc)
temp_files = list(SRC.glob("*")) 
remaining = []
for f in temp_files:
    if f.is_file() and f.suffix.lower() not in {'.chd'}:
        remaining.append(f)

if remaining:
    print(f"\nArquivos temp restantes: {len(remaining)}")
    for f in remaining[:10]:
        print(f"  {f.name} ({f.stat().st_size/1024/1024:.1f}MB)")
    # Apagar temps
    for f in remaining:
        try:
            f.unlink()
        except:
            pass

print(f"\nTotal: {moved} movidos, {skipped} pulados (ja existiam)")
