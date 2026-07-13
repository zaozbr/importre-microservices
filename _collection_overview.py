#!/usr/bin/env python3
"""Panorama geral da colecao PSX — ignora D:\\roms\\duplicados."""
import sys, re, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
FALTANTES = Path(r"D:\roms\library\roms\PSX_Colecao_Faltantes.md")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# 1. Indexar CHDs por serial (apenas psx/)
chd_serials = set()
chd_files = list(PSX.glob("*.chd"))
for c in chd_files:
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
    if m:
        chd_serials.add(m.group(1).upper())

print(f"=== COLECAO PSX - PANORAMA GERAL ===")
print()
print(f"CHDs existentes: {len(chd_files)}")
print(f"  Seriais unicos: {len(chd_serials)}")

# 2. BINs/CUEs/ECMs sem CHD em psx/ (apenas)
bins_sem_chd = []
cues_com_bin_sem_chd = []
cues_sem_bin = []
ecms_sem_chd = []

# Indexar BINs referenciados por CUEs (para nao contar como "sem CUE")
cue_referenced_bins = set()
for cue in PSX.rglob("*.cue"):
    try:
        content = cue.read_text(encoding="utf-8", errors="replace")
        refs = re.findall(r'FILE\s+"([^"]+)"', content)
        for ref in refs:
            cue_referenced_bins.add(Path(ref).name.lower())
    except: pass

for cue in PSX.rglob("*.cue"):
    if "nao-conversivel" in cue.name.lower():
        continue
    serial = extract_serial(cue.stem)
    if serial and serial in chd_serials:
        continue
    try:
        content = cue.read_text(encoding="utf-8", errors="replace")
    except:
        continue
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    has_bin = any((cue.parent / r).exists() for r in refs)
    if has_bin:
        cues_com_bin_sem_chd.append(cue)
    else:
        cues_sem_bin.append(cue)

# BINs sem CUE nao sao mais contados — sao orfaos movidos para duplicados
# bins_sem_chd permanece vazio

for f in PSX.rglob("*.ecm"):
    serial = extract_serial(f.stem)
    if serial and serial in chd_serials:
        continue
    ecms_sem_chd.append(f)

# 3. Lista de faltantes (deduplicada)
faltantes_serials = set()
if FALTANTES.exists():
    content = FALTANTES.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r'([A-Z]{2,4}[-]\d{3,5})', content):
        faltantes_serials.add(m.group(1).upper())

# 4. Fila do importre
queue_serials = set()
try:
    q = Path(r"D:\roms\library\roms\_importre_state\queue.json")
    if q.exists():
        data = json.loads(q.read_text(encoding="utf-8"))
        for item in data.get("queue", []):
            s = item.get("serial", "").upper()
            if s:
                queue_serials.add(s)
        for k in data.get("in_progress", {}).keys():
            queue_serials.add(k.upper())
        for k in data.get("completed", {}).keys():
            queue_serials.add(k.upper())
except Exception:
    pass

# 5. Calcular faltantes reais (nao tem CHD)
faltantes_sem_chd = faltantes_serials - chd_serials
faltantes_com_chd = faltantes_serials & chd_serials

# 6. Resumo
print()
print(f"=== ROMs SEM CHD (precisam converter) ===")
print(f"  CUEs com BIN (pronto p/ converter):  {len(cues_com_bin_sem_chd)}")
print(f"  BINs sem CUE (precisa gerar CUE):    {len(bins_sem_chd)}")
print(f"  ECMs (precisa descomprimir):         {len(ecms_sem_chd)}")
print(f"  CUEs sem BIN (precisa download):     {len(cues_sem_bin)}")
print(f"  TOTAL sem CHD:                       {len(cues_com_bin_sem_chd)+len(bins_sem_chd)+len(ecms_sem_chd)+len(cues_sem_bin)}")

print()
print(f"=== FALTANTES (lista deduplicada) ===")
print(f"  Total na lista de faltantes:         {len(faltantes_serials)}")
print(f"  Ja tem CHD (completos):              {len(faltantes_com_chd)}")
print(f"  Faltam (sem CHD):                    {len(faltantes_sem_chd)}")
print(f"  Na fila do importre:                 {len(queue_serials & faltantes_sem_chd)}")
print(f"  Nao na fila (precisa adicionar):     {len(faltantes_sem_chd - queue_serials)}")

print()
print(f"=== RESUMO FINAL ===")
print(f"  Colecao completa (CHD):              {len(chd_serials)} jogos")
print(f"  Faltam para completar:               {len(faltantes_sem_chd)} jogos")
print(f"  Pendentes de conversao:              {len(cues_com_bin_sem_chd)+len(bins_sem_chd)+len(ecms_sem_chd)} arquivos")
print(f"  Pendentes de download:               {len(cues_sem_bin)} CUEs sem BIN")
print(f"  % completo:                          {100*len(faltantes_com_chd)/max(len(faltantes_serials),1):.1f}%")
