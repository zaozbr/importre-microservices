#!/usr/bin/env python3
"""Diagnostico: por que scan_roms so encontra 8 itens quando overview conta 318?"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
CHD_OUTPUT_DIR = Path(r"F:\chd_temp")

def extract_serial(filename):
    m = re.search(r"(SLUS|SLES|SCES|SLPS|SLPM|SCPS|SCUS|SLKA|SCED|SIPS|PAPX|SLED|PCPX|PBPX|SCZS|SCPM|ESPM|PUPX|PTPX|PEPX|SCAJ|PCPD|PSRM|NYMC)[-_]?(\d{4,5})", filename, re.I)
    if m:
        return f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
    return ""

def _normalize_stem_for_fuzzy(stem):
    s = stem
    s = re.sub(r'\[?[A-Z]{2,4}[-]\d{3,5}\]?', '', s)
    s = re.sub(r'\(Track \d+\)', '', s, flags=re.I)
    s = re.sub(r'\(v?\d+(?:\.\d+)?(?:[a-z]?)\)', '', s, flags=re.I)
    regions = r'Japan|USA|Europe|Germany|France|Spain|Italy|Netherlands|Sweden|Australia|Korea|Brazil|Canada|World|United Kingdom|UK|Russia|China|Asia|En,Fr,De,Es,It|En,Fr,De|En,Fr|Fr,De|Ja,En|Fr,Es|De,Es|Multi|English|Japanese'
    s = re.sub(rf'\(({regions}|(?:[A-Za-z]{{2,8}}, )*[A-Za-z]{{2,8}})\)', '', s, flags=re.I)
    single_regions = 'J|E|U|G|F|S|I|K|B|A|C|W|R|H|T|N|M|P'
    s = re.sub(rf'\((?:{single_regions})(?:,\s*(?:{single_regions}))*\)', '', s, flags=re.I)
    s = re.sub(r'\(?\[?Disc\s*\d+(?:of\d+)?\]?\)?', '', s, flags=re.I)
    s = s.replace('-', ' ')
    s = re.sub(r'\s+', ' ', s)
    return s.strip(' ._-\t\r\n')

def sanitize_filename(name):
    INVALID_CHARS = '<>:"/\\|?*'
    for c in INVALID_CHARS:
        name = name.replace(c, "")
    if len(name) > 180:
        name = name[:180]
    return name.strip().rstrip(".")

def build_chd_name(serial, name):
    base = name
    is_homebrew = serial and serial.startswith(("HBREW", "HOMEBREW"))
    if serial and not is_homebrew:
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
    if serial and not is_homebrew:
        base = f"{base}-{serial}"
    return sanitize_filename(base) + ".chd"

# CHDs
chd_files = list(PSX.glob("*.chd")) + list(CHD_OUTPUT_DIR.glob("*.chd"))
chds = {f.stem.lower() for f in chd_files}
chds = chds | {sanitize_filename(f.stem).lower() for f in chd_files}
chds_norm = {}
for f in chd_files:
    norm = _normalize_stem_for_fuzzy(f.stem).lower()
    if norm:
        chds_norm.setdefault(norm, f.stem)

print(f"CHDs indexados: {len(chds)} stems, {len(chds_norm)} normalizados")

# Contar CUEs
cues = list(PSX.rglob("*.cue"))
# Filtrar nao-conversivel
cues = [c for c in cues if "nao-conversivel" not in c.name.lower()]
print(f"CUEs em psx/: {len(cues)}")

# Filtrar como scan_roms faz
track_pattern = re.compile(r"\(Track \d+\)", re.I)
skipped_no_bin = 0
skipped_has_chd = 0
skipped_fuzzy = 0
skipped_dup_serial = 0
items = []
seen_serials = set()

for cue in cues:
    # Verificar se tem BIN
    content = cue.read_text(encoding="utf-8", errors="replace")
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    has_bin = any((cue.parent / r).exists() for r in refs)
    if not has_bin:
        skipped_no_bin += 1
        continue

    serial = extract_serial(cue.name)
    expected_chd = Path(build_chd_name(serial, cue.stem)).stem.lower()
    norm = re.sub(r"\(track \d+\)", "", cue.stem.lower(), flags=re.I).strip()

    if expected_chd in chds:
        skipped_has_chd += 1
        continue
    if not serial and any(norm[:20] in c for c in chds):
        skipped_has_chd += 1
        continue
    if _normalize_stem_for_fuzzy(cue.stem).lower() in chds_norm:
        skipped_fuzzy += 1
        continue
    if serial and serial in seen_serials:
        skipped_dup_serial += 1
        continue
    if serial:
        seen_serials.add(serial)
    items.append((serial, cue.name))

print(f"\nResultados:")
print(f"  Sem BIN:           {skipped_no_bin}")
print(f"  Ja tem CHD:        {skipped_has_chd}")
print(f"  Fuzzy match CHD:   {skipped_fuzzy}")
print(f"  Serial duplicado:  {skipped_dup_serial}")
print(f"  ITENS PARA CONVERTER: {len(items)}")
print(f"\nPrimeiros 20 itens:")
for s, n in items[:20]:
    print(f"  {s:15s} {n[:60]}")
