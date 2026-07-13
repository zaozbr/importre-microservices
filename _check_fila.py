import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

d = Path(r"D:\roms\library\roms\psx\_fila_conversao")
cues = list(d.glob("*.cue"))
bins = list(d.glob("*.bin"))
imgs = list(d.glob("*.img"))
isos = list(d.glob("*.iso"))
print(f"_fila_conversao: {len(cues)} CUEs, {len(bins)} BINs, {len(imgs)} IMGs, {len(isos)} ISOs")

with_bin = 0
without_bin = 0
for cue in cues:
    content = cue.read_text(encoding="utf-8", errors="replace")
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    has_bin = any((cue.parent / r).exists() for r in refs)
    if has_bin:
        with_bin += 1
    else:
        without_bin += 1
        if without_bin <= 5:
            print(f"  SEM BIN: {cue.name[:60]}")

print(f"  Com BIN: {with_bin}")
print(f"  Sem BIN: {without_bin}")
