"""Relatorio de status atual da colecao PSX."""
from pathlib import Path
import re
import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _chd_convert_v2 import build_chd_name, extract_serial

PSX_DIR = Path(r"D:\roms\library\roms\psx")
CHD_OUTPUT_DIR = Path(r"F:\chd_temp")

# Contagens
chd_files = list(PSX_DIR.glob("*.chd"))
cue_files = list(PSX_DIR.glob("*.cue"))
bin_files = list(PSX_DIR.glob("*.bin"))
iso_files = list(PSX_DIR.glob("*.iso"))
img_files = list(PSX_DIR.glob("*.img"))
mdf_files = list(PSX_DIR.glob("*.mdf"))
ecm_files = list(PSX_DIR.glob("*.ecm"))

failed_files = list((PSX_DIR / "_chd_failed").glob("*")) if (PSX_DIR / "_chd_failed").exists() else []
dup_files = list((PSX_DIR / "duplicados").glob("*")) if (PSX_DIR / "duplicados").exists() else []

print("=" * 60)
print("ESTADO ATUAL DA COLECAO PSX")
print("=" * 60)
print(f"CHDs prontos:           {len(chd_files)}")
print(f"CUEs:                   {len(cue_files)}")
print(f"BINs:                   {len(bin_files)}")
print(f"ISOs:                   {len(iso_files)}")
print(f"IMGs:                   {len(img_files)}")
print(f"MDFs:                   {len(mdf_files)}")
print(f"ECMs:                   {len(ecm_files)}")
print(f"Falhas (_chd_failed):   {len(failed_files)}")
print(f"Duplicados:             {len(dup_files)}")

# Total de jogos (CHDs + arquivos sem CHD)
all_rom_exts = {".cue", ".bin", ".iso", ".img", ".mdf", ".ecm"}
rom_files = [f for f in PSX_DIR.iterdir() if f.is_file() and f.suffix.lower() in all_rom_exts]

chd_set = {f.name.lower() for f in chd_files}
chd_set |= {f.name.lower() for f in CHD_OUTPUT_DIR.glob("*.chd")}

missing = []
for f in rom_files:
    serial = extract_serial(f.name)
    name = re.sub(r"\(Track \d+\)", "", f.stem, flags=re.I).strip()
    expected = build_chd_name(serial, name).lower()
    if expected not in chd_set:
        missing.append(f.name)

print(f"\nArquivos ROM sem CHD correspondente: {len(missing)}")
for m in missing:
    print(f"  - {m}")

print(f"\nItens em _chd_failed:")
for f in sorted(failed_files):
    print(f"  - {f.name}")

print(f"\nTotal de jogos distintos (CHD + sem CHD): {len(chd_files) + len(missing)}")
