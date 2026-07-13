#!/usr/bin/env python3
"""Diagnostico: quantos dos 300 CUEs com BIN do overview JA TEM CHD via fuzzy?"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
CHD_OUTPUT_DIR = Path(r"F:\chd_temp")

def extract_serial(filename):
    m = re.search(r"(SLUS|SLES|SCES|SLPS|SLPM|SCPS|SCUS|SLKA|SCED|SIPS|PAPX|SLED|PCPX|PBPX|SCZS|SCPM|ESPM|PUPX|PTPX|PEPX|SCAJ|PCPD|PSRM|NYMC)[-_]?(\d{4,5})", filename, re.I)
    if m: return f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
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
    for c in '<>:"/\\|?*': name = name.replace(c, "")
    if len(name) > 180: name = name[:180]
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
    if serial and not is_homebrew: base = f"{base}-{serial}"
    return sanitize_filename(base) + ".chd"

# CHDs
chd_files = list(PSX.glob("*.chd")) + list(CHD_OUTPUT_DIR.glob("*.chd"))
chds = {f.stem.lower() for f in chd_files}
chds = chds | {sanitize_filename(f.stem).lower() for f in chd_files}
chds_norm = {}
for f in chd_files:
    norm = _normalize_stem_for_fuzzy(f.stem).lower()
    if norm: chds_norm.setdefault(norm, f.stem)

# CUEs com BIN (como overview conta)
cues_com_bin = []
cues_sem_bin = []
bins_sem_cue = []
cue_referenced_bins = set()
for cue in PSX.rglob("*.cue"):
    try:
        content = cue.read_text(encoding="utf-8", errors="replace")
        refs = re.findall(r'FILE\s+"([^"]+)"', content)
        for ref in refs: cue_referenced_bins.add(Path(ref).name.lower())
    except: pass

for cue in PSX.rglob("*.cue"):
    if "nao-conversivel" in cue.name.lower(): continue
    serial = extract_serial(cue.name)
    if serial and serial in {extract_serial(c.stem) for c in chd_files if extract_serial(c.stem)}: continue
    try: content = cue.read_text(encoding="utf-8", errors="replace")
    except: continue
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    has_bin = any((cue.parent / r).exists() for r in refs)
    if has_bin: cues_com_bin.append((cue, serial))
    else: cues_sem_bin.append((cue, serial))

for f in PSX.rglob("*.bin"):
    if "nao-conversivel" in f.name.lower(): continue
    serial = extract_serial(f.name)
    if serial and serial in {extract_serial(c.stem) for c in chd_files if extract_serial(c.stem)}: continue
    if f.with_suffix(".cue").exists(): continue
    if f.name.lower() in cue_referenced_bins: continue
    bins_sem_cue.append((f, serial))

print(f"=== CONTAGEM OVERVIEW (serial-only) ===")
print(f"  CUEs com BIN:   {len(cues_com_bin)}")
print(f"  CUEs sem BIN:   {len(cues_sem_bin)}")
print(f"  BINs sem CUE:   {len(bins_sem_cue)}")

# Agora aplicar logica do scan_roms (fuzzy)
ja_tem_chd_exact = 0
ja_tem_chd_fuzzy = 0
ja_tem_chd_substring = 0
realmente_precisa = 0

for cue, serial in cues_com_bin:
    expected_chd = Path(build_chd_name(serial, cue.stem)).stem.lower()
    norm = re.sub(r"\(track \d+\)", "", cue.stem.lower(), flags=re.I).strip()
    if expected_chd in chds:
        ja_tem_chd_exact += 1
    elif not serial and any(norm[:20] in c for c in chds):
        ja_tem_chd_substring += 1
    elif serial and _normalize_stem_for_fuzzy(cue.stem).lower() in chds_norm:
        ja_tem_chd_fuzzy += 1
    elif not serial and _normalize_stem_for_fuzzy(cue.stem).lower() in chds_norm:
        ja_tem_chd_fuzzy += 1
    else:
        realmente_precisa += 1

print(f"\n=== ANALISE FUZZY (como scan_roms ve) ===")
print(f"  Ja tem CHD (nome exato):     {ja_tem_chd_exact}")
print(f"  Ja tem CHD (substring):      {ja_tem_chd_substring}")
print(f"  Ja tem CHD (fuzzy match):    {ja_tem_chd_fuzzy}")
print(f"  REALMENTE PRECISA CONVERTER: {realmente_precisa}")

# Mostrar os que realmente precisam
print(f"\n=== CUEs que REALMENTE precisam converter ===")
for cue, serial in cues_com_bin:
    expected_chd = Path(build_chd_name(serial, cue.stem)).stem.lower()
    norm = re.sub(r"\(track \d+\)", "", cue.stem.lower(), flags=re.I).strip()
    fuzzy = _normalize_stem_for_fuzzy(cue.stem).lower()
    if (expected_chd in chds or 
        (not serial and any(norm[:20] in c for c in chds)) or
        fuzzy in chds_norm):
        continue
    print(f"  {serial:12s} {cue.name[:60]}")

# BINs sem CUE
print(f"\n=== BINs sem CUE que precisam gerar CUE ===")
for f, serial in bins_sem_cue:
    print(f"  {serial:12s} {f.name[:60]}")
