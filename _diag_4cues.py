#!/usr/bin/env python3
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
    for c in '<>:"/\\|?*':
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

chd_files = list(PSX.glob("*.chd")) + list(CHD_OUTPUT_DIR.glob("*.chd"))
chds = {f.stem.lower() for f in chd_files}
chds = chds | {sanitize_filename(f.stem).lower() for f in chd_files}
chds_norm = {}
for f in chd_files:
    norm = _normalize_stem_for_fuzzy(f.stem).lower()
    if norm:
        chds_norm.setdefault(norm, f.stem)

test_cues = [
    "Langrisser IV & V Final Edition (Japan) (Disc 1) (Track 1).cue",
    "Option - Tuning Car Battle (Japan) (Track 01).cue",
    "Ridge Racer Revolution (Japan) (Track 01).cue",
    "SuperLite 1500 Series - Shougi II (Japan) (Track 1).cue",
]

for name in test_cues:
    cue = PSX / name
    serial = extract_serial(cue.name)
    expected_chd = Path(build_chd_name(serial, cue.stem)).stem.lower()
    norm = re.sub(r"\(track \d+\)", "", cue.stem.lower(), flags=re.I).strip()
    in_expected = expected_chd in chds
    in_substring = not serial and any(norm[:20] in c for c in chds)
    fuzzy_norm = _normalize_stem_for_fuzzy(cue.stem).lower()
    in_fuzzy = fuzzy_norm in chds_norm
    print(f"{name[:50]:50s} serial={serial!r:12s} expected={in_expected} substr={in_substring} fuzzy={in_fuzzy}")
    if in_substring:
        matches = [c for c in chds if norm[:20] in c]
        print(f"  substring matches: {matches[:5]}")
    if in_fuzzy:
        print(f"  fuzzy match: {chds_norm[fuzzy_norm]}")
