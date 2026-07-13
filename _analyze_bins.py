#!/usr/bin/env python3
"""Analisa BINs sem CUE e os categoriza:
- standalone: BIN unico que precisa de CUE gerado
- track_2plus: Track 2/3/4... que pertence a um CUE existente
- has_chd: ja tem CHD (ignorar)
- has_img: tem IMG equivalente (duplicado)
- too_small: < 1MB, provavelmente nao e jogo
- duplicate: mesmo nome/stem de outro BIN
"""
import sys, re, json, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# 1. Indexar CHDs por serial e por stem
chd_serials = set()
chd_stems = set()
for base in [PSX, DUP]:
    if not base.exists(): continue
    for c in base.glob("*.chd"):
        chd_stems.add(c.stem.lower())
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
        if m: chd_serials.add(m.group(1).upper())

# 2. Indexar CUEs existentes (por stem e por nome do BIN referenciado)
cue_stems = set()
cue_referenced_bins = set()
for base in [PSX, DUP]:
    if not base.exists(): continue
    for cue in base.glob("*.cue"):
        cue_stems.add(cue.stem.lower())
        try:
            content = cue.read_text(encoding="utf-8", errors="replace")
            refs = re.findall(r'FILE\s+"([^"]+)"', content)
            for ref in refs:
                cue_referenced_bins.add(Path(ref).name.lower())
                cue_referenced_bins.add(Path(ref).stem.lower())
        except: pass

# 3. Indexar IMGs (para detectar BIN+IMG duplicados)
img_stems = set()
for base in [PSX, DUP]:
    if not base.exists(): continue
    for f in base.glob("*.img"):
        img_stems.add(f.stem.lower())

# 4. Coletar BINs sem CUE
categories = {
    "standalone": [],      # precisa de CUE gerado
    "track_2plus": [],     # track 2+ de multi-track
    "has_chd": [],         # ja tem CHD
    "has_img": [],         # tem IMG equivalente
    "too_small": [],       # < 1MB
    "referenced_by_cue": [], # ja referenciado por um CUE existente
}

for base, label in [(PSX, "psx"), (DUP, "dup")]:
    if not base.exists(): continue
    for f in base.glob("*.bin"):
        stem = f.stem
        stem_lower = stem.lower()
        serial = extract_serial(stem)
        size_mb = f.stat().st_size / (1024*1024)

        # Ja tem CHD?
        if serial and serial in chd_serials:
            categories["has_chd"].append({"path": str(f), "stem": stem, "serial": serial, "size_mb": size_mb, "location": label})
            continue
        if stem_lower in chd_stems:
            categories["has_chd"].append({"path": str(f), "stem": stem, "serial": serial, "size_mb": size_mb, "location": label})
            continue

        # Tem CUE com mesmo stem?
        if stem_lower in cue_stems:
            categories["has_chd"].append({"path": str(f), "stem": stem, "serial": serial, "size_mb": size_mb, "location": label})
            continue

        # Referenciado por algum CUE?
        if stem_lower in cue_referenced_bins or f.name.lower() in cue_referenced_bins:
            categories["referenced_by_cue"].append({"path": str(f), "stem": stem, "serial": serial, "size_mb": size_mb, "location": label})
            continue

        # Track 2+?
        if re.search(r'Track\s*[2-9]|Track\s*1[0-9]|Track\s*0[2-9]', stem, re.I):
            categories["track_2plus"].append({"path": str(f), "stem": stem, "serial": serial, "size_mb": size_mb, "location": label})
            continue

        # Tem IMG equivalente?
        if stem_lower in img_stems:
            categories["has_img"].append({"path": str(f), "stem": stem, "serial": serial, "size_mb": size_mb, "location": label})
            continue

        # Muito pequeno?
        if size_mb < 1.0:
            categories["too_small"].append({"path": str(f), "stem": stem, "serial": serial, "size_mb": size_mb, "location": label})
            continue

        # Standalone - precisa de CUE
        categories["standalone"].append({"path": str(f), "stem": stem, "serial": serial, "size_mb": size_mb, "location": label})

# Salvar analise
Path(r"D:\roms\library\roms\psx\_bins_analysis.json").write_text(
    json.dumps(categories, indent=2, ensure_ascii=False), encoding='utf-8'
)

print("=== ANALISE DE BINS SEM CUE ===")
print()
for cat, items in categories.items():
    total_size = sum(i["size_mb"] for i in items)
    print(f"  {cat:25s}: {len(items):5d} itens ({total_size/1024:.1f} GB)")
print()
total = sum(len(v) for v in categories.values())
print(f"  TOTAL:                   {total:5d} itens")
print()
print("=== STANDALONE (primeiros 20) ===")
for item in categories["standalone"][:20]:
    print(f"  {item['stem'][:55]:55s} {item['size_mb']:8.1f}MB  [{item['location']}]")
