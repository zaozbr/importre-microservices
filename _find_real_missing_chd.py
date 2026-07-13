"""Lista arquivos nao-CHD em psx que realmente nao tem CHD correspondente (por expected_chd)."""
from pathlib import Path
import re

PSX_DIR = Path(r"D:\roms\library\roms\psx")
CHD_OUTPUT_DIR = Path(r"F:\chd_temp")
ROM_EXTS = {".bin", ".iso", ".img", ".mdf", ".ecm", ".cue"}

def sanitize_filename(name):
    INVALID_CHARS = '<>:"/\\|?*'
    for c in INVALID_CHARS:
        name = name.replace(c, "")
    if len(name) > 180:
        name = name[:180]
    return name.strip().rstrip(".")

def extract_serial(filename):
    m = re.search(r"(SLUS|SLES|SCES|SLPS|SLPM|SCPS|SCUS|SLKA|SCED|SIPS|PAPX|SLED|PCPX|PBPX|SCZS|SCPM|ESPM|PUPX|PTPX|PEPX|SCAJ|PCPD|PSRM|NYMC)[-_]?(\d{4,5})", filename, re.I)
    if m:
        return f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
    return ""

def build_chd_name(serial, name):
    base = name
    if serial:
        base = re.sub(r"[\-_]?\s*" + re.escape(serial), "", base, flags=re.I)
        serial_nodash = serial.replace("-", "")
        base = re.sub(r"[\-_]?\s*" + serial_nodash, "", base, flags=re.I)
    base = re.sub(r"\(Disc \d+\)", "", base, flags=re.I).strip()
    base = re.sub(r"\(Track \d+\)", "", base, flags=re.I).strip()
    base = re.sub(r"\(.*?\)", "", base).strip()
    base = re.sub(r"[^\w\s-]", "", base)
    base = re.sub(r"\s+", "-", base)
    base = re.sub(r"-+", "-", base)
    base = base.strip("-")
    if serial:
        base = f"{base}-{serial}"
    return sanitize_filename(base) + ".chd"

chd_set = {f.name.lower() for f in (list(PSX_DIR.glob("*.chd")) + list(CHD_OUTPUT_DIR.glob("*.chd")))}

missing = []
for f in PSX_DIR.iterdir():
    if not f.is_file() or f.suffix.lower() not in ROM_EXTS:
        continue
    serial = extract_serial(f.name)
    name = re.sub(r"\(Track \d+\)", "", f.stem, flags=re.I).strip()
    expected = build_chd_name(serial, name).lower()
    if expected not in chd_set:
        missing.append((f.name, expected))

print(f"Arquivos realmente sem CHD correspondente: {len(missing)}")
for fname, expected in missing:
    print(f"  {fname}  -> esperado: {expected}")
