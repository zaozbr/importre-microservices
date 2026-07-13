#!/usr/bin/env python3
"""Diagnostico: por que os 3 CUEs multi-track nao aparecem no scan_roms?"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")

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

def _base_key(name):
    return _normalize_stem_for_fuzzy(Path(name).stem).lower()

track_pattern = re.compile(r"\(Track \d+\)", re.I)
track_groups = {}
for pattern in ["*.cue", "*.bin", "*.iso", "*.img", "*.mdf", "*.ecm"]:
    for f in PSX.rglob(pattern):
        if track_pattern.search(f.name):
            key = _base_key(f.name)
            track_groups.setdefault(key, []).append(f)
multi_track_bases = {key for key, files in track_groups.items() if len(files) >= 2}

print(f"multi_track_bases: {len(multi_track_bases)}")
for key, files in track_groups.items():
    if len(files) >= 2:
        print(f"  {key}: {len(files)} files")
        for f in files[:3]:
            print(f"    {f.name[:60]}")

# Checar os 3 CUEs
test_cues = [
    "Langrisser IV & V Final Edition (Japan) (Disc 1) (Track 1).cue",
    "Option - Tuning Car Battle (Japan) (Track 01).cue",
    "SuperLite 1500 Series - Shougi II (Japan) (Track 1).cue",
]
print("\n=== Teste dos 3 CUEs ===")
for name in test_cues:
    p = PSX / name
    if not p.exists():
        # rglob
        matches = list(PSX.rglob(name))
        if matches:
            p = matches[0]
        else:
            print(f"  NAO ENCONTRADO: {name}")
            continue
    has_track = bool(track_pattern.search(p.name))
    key = _base_key(p.name)
    in_multi = key in multi_track_bases
    print(f"  {p.name[:50]:50s} track={has_track} key={key[:30]} in_multi={in_multi}")
    if in_multi:
        print(f"    Files in group: {[f.name[:40] for f in track_groups[key]]}")
