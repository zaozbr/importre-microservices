#!/usr/bin/env python3
"""Lista CUEs em psx/ que ainda tem BIN mas nao tem CHD correspondente (potenciais problemas de conversao)."""
import sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")

def extract_serial(name):
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", name, re.I)
    return m.group(1).upper() if m else None

def normalize(s):
    s = re.sub(r'\[?[A-Z]{2,4}[-]\d{3,5}\]?', '', s)
    s = re.sub(r'\(Track\s*\d+\)', '', s, flags=re.I)
    s = re.sub(r'\(Disc\s*\d+\)', '', s, flags=re.I)
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()

chd_serials = set()
chd_norms = set()
for c in PSX.glob("*.chd"):
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", c.stem, re.I)
    if m: chd_serials.add(m.group(1).upper())
    chd_norms.add(normalize(c.stem))

cues_com_bin_sem_chd = []
cues_sem_bin = []
cues_nao_conversivel = []

for cue in PSX.rglob("*.cue"):
    if "nao-conversivel" in cue.name.lower():
        cues_nao_conversivel.append(cue)
        continue
    serial = extract_serial(cue.stem)
    norm = normalize(cue.stem)
    has_chd = (serial and serial in chd_serials) or (norm in chd_norms)
    try:
        content = cue.read_text(encoding="utf-8", errors="replace")
    except:
        continue
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    has_bin = any((cue.parent / r).exists() for r in refs)
    if has_chd:
        continue
    if has_bin:
        cues_com_bin_sem_chd.append((cue, serial))
    else:
        cues_sem_bin.append((cue, serial))

print(f"=== CUEs em psx/ ===")
print(f"  Com BIN, sem CHD (problemas de conversao): {len(cues_com_bin_sem_chd)}")
print(f"  Sem BIN (precisa download):                {len(cues_sem_bin)}")
print(f"  Marcados nao-conversivel:                  {len(cues_nao_conversivel)}")

if cues_com_bin_sem_chd:
    print(f"\n--- CUEs com BIN sem CHD (problemas) ---")
    for cue, serial in cues_com_bin_sem_chd:
        print(f"  {serial or '':12s} {cue.relative_to(PSX)}")

if cues_sem_bin:
    print(f"\n--- CUEs sem BIN ---")
    for cue, serial in cues_sem_bin:
        print(f"  {serial or '':12s} {cue.relative_to(PSX)}")

if cues_nao_conversivel:
    print(f"\n--- CUEs nao-conversivel ---")
    for cue in cues_nao_conversivel:
        print(f"  {cue.relative_to(PSX)}")
