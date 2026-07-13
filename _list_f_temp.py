from pathlib import Path
F = Path(r"F:\chd_temp")
bins = list(F.glob("*.bin"))
cues = list(F.glob("*.cue"))
chds = list(F.glob("*.chd"))
print(f"BINs: {len(bins)}")
print(f"CUEs: {len(cues)}")
print(f"CHDs: {len(chds)}")
print()
for f in bins:
    print(f"  BIN  {f.name[:70]:70s} {f.stat().st_size//1024//1024}MB")
for f in cues:
    print(f"  CUE  {f.name[:70]:70s}")
for f in chds:
    sz = f.stat().st_size
    print(f"  CHD  {f.name[:70]:70s} {sz//1024}KB")
