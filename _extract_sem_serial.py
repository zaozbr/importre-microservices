#!/usr/bin/env python3
"""Extrai lista de CUEs sem serial de D:\roms\duplicados e psx/ (sem CHD)."""
import sys, re, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# Indexar CHDs por serial
chd_serials = set()
for base in [PSX, DUP]:
    if not base.exists(): continue
    for c in base.glob("*.chd"):
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
        if m: chd_serials.add(m.group(1).upper())

# Coletar CUEs sem BIN e sem serial
cues_sem_bin_sem_serial = []
cues_sem_bin_com_serial = []
for base in [PSX, DUP]:
    if not base.exists(): continue
    for cue in base.glob("*.cue"):
        serial = extract_serial(cue.stem)
        if serial and serial in chd_serials: continue
        try:
            content = cue.read_text(encoding="utf-8", errors="replace")
        except: continue
        refs = re.findall(r'FILE\s+"([^"]+)"', content)
        if not refs: continue
        missing = [r for r in refs if not (cue.parent / r).exists()]
        if not missing: continue  # tem BIN
        # Realmente sem BIN
        if serial:
            cues_sem_bin_com_serial.append({"cue": cue.name, "serial": serial, "stem": cue.stem})
        else:
            # Limpar nome para busca
            name = cue.stem
            # Remover (Disc X), (Japan), etc para nome mais limpo
            clean = re.sub(r'\s*\(Disc \d+\).*$', '', name)
            clean = re.sub(r'\s*\(Japan\).*$', '', clean, flags=re.I)
            clean = re.sub(r'\s*\(Europe\).*$', '', clean, flags=re.I)
            clean = re.sub(r'\s*\(USA\).*$', '', clean, flags=re.I)
            clean = clean.strip()
            cues_sem_bin_sem_serial.append({"cue": cue.name, "stem": cue.stem, "clean": clean})

# Salvar
out = {
    "com_serial": cues_sem_bin_com_serial,
    "sem_serial": cues_sem_bin_sem_serial,
}
Path(r"D:\roms\library\roms\psx\_cues_sem_serial.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8'
)

print(f"Com serial (ja adicionados ao importre): {len(cues_sem_bin_com_serial)}")
print(f"Sem serial (precisam busca web):         {len(cues_sem_bin_sem_serial)}")
print()
print("=== SEM SERIAL (primeiros 20) ===")
for item in cues_sem_bin_sem_serial[:20]:
    print(f"  {item['clean'][:60]}")
