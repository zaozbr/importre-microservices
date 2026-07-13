#!/usr/bin/env python3
"""Analisa os 671 skips do importre e identifica quais precisam de re-download.
Criterios:
- Tem CHD -> skip correto, nao precisa baixar
- Tem BIN/CUE mas sem CHD -> precisa converter, nao baixar
- Nao tem nada (nem CHD nem BIN) -> precisa re-download
"""
import sys, json, re, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = PSX / "duplicados"
QUEUE_FILE = Path(r"D:\roms\library\roms\_importre_state\queue.json")
MISSING_FILE = Path(r"D:\roms\library\roms\PSX_Colecao_Faltantes.md")
NEED_REDOWNLOAD = Path(r"D:\roms\library\roms\psx\_need_redownload.json")
DEST_DIR = Path(r"D:\roms\psxduplicas")

ROM_EXTS = {".bin", ".img", ".iso", ".mdf", ".cue", ".ccd", ".sub"}

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# 1. Carregar lista de faltantes (origem dos skips)
print("Carregando lista de faltantes...")
missing_items = []
if MISSING_FILE.exists():
    for line in MISSING_FILE.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('Total'):
            continue
        # Formato esperado: serial | nome | regiao | tipo
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 1:
            serial = parts[0]
            name = parts[1] if len(parts) > 1 else ''
            region = parts[2] if len(parts) > 2 else ''
            missing_items.append({'serial': serial, 'name': name, 'region': region})
else:
    print(f"Arquivo nao encontrado: {MISSING_FILE}")

print(f"Total na lista de faltantes: {len(missing_items)}")

# 2. Carregar fila atual
print("Carregando fila do importre...")
data = json.loads(QUEUE_FILE.read_text(encoding='utf-8'))
queue_serials = set()
for item in data.get('queue', []):
    s = item.get('serial', '')
    if s:
        queue_serials.add(s.upper())
in_prog_serials = set(k.upper() for k in data.get('in_progress', {}).keys())
completed_serials = set(k.upper() for k in data.get('completed', {}).keys())
failed_serials = set(k.upper() for k in data.get('failed', {}).keys())

print(f"  Queue (pending): {len(queue_serials)}")
print(f"  In progress: {len(in_prog_serials)}")
print(f"  Completed: {len(completed_serials)}")
print(f"  Failed: {len(failed_serials)}")

# 3. Skips = itens da lista de faltantes que NAO estao na fila
all_in_queue = queue_serials | in_prog_serials | completed_serials | failed_serials
skip_items = []
for item in missing_items:
    serial = item.get('serial', '').upper()
    if serial and serial not in all_in_queue:
        skip_items.append(item)

print(f"  Skips (na lista mas nao na fila): {len(skip_items)}")

# 4. Construir indice de arquivos na pasta
print("Indexando arquivos da colecao...")
chd_serials = set()
rom_serials = set()  # tem BIN/IMG/ISO mas pode nao ter CHD
cue_serials = set()

for f in PSX.iterdir():
    if not f.is_file():
        continue
    ext = f.suffix.lower()
    serial = extract_serial(f.name)
    if not serial:
        continue
    if ext == '.chd':
        chd_serials.add(serial)
    elif ext in ROM_EXTS:
        rom_serials.add(serial)
    elif ext == '.cue':
        cue_serials.add(serial)

if DUP.exists():
    for f in DUP.iterdir():
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        serial = extract_serial(f.name)
        if not serial:
            continue
        if ext == '.chd':
            chd_serials.add(serial)
        elif ext in ROM_EXTS:
            rom_serials.add(serial)
        elif ext == '.cue':
            cue_serials.add(serial)

print(f"  CHDs (por serial): {len(chd_serials)}")
print(f"  ROMs sem CHD (por serial): {len(rom_serials)}")
print(f"  CUEs (por serial): {len(cue_serials)}")

# 5. Categorizar skips
has_chd = []
has_rom_no_chd = []
has_cue_no_rom = []
need_download = []

for item in skip_items:
    serial = item.get('serial', '').upper()
    if serial in chd_serials:
        has_chd.append(item)
    elif serial in rom_serials:
        has_rom_no_chd.append(item)
    elif serial in cue_serials:
        has_cue_no_rom.append(item)
    else:
        need_download.append(item)

print(f"\n=== ANALISE DOS {len(skip_items)} SKIPS ===")
print(f"  Tem CHD (skip correto):         {len(has_chd)}")
print(f"  Tem BIN/IMG mas sem CHD:        {len(has_rom_no_chd)}")
print(f"  Tem CUE mas sem BIN:            {len(has_cue_no_rom)}")
print(f"  Nao tem nada (precisa download): {len(need_download)}")
print(f"  TOTAL precisam re-download:      {len(need_download) + len(has_cue_no_rom)}")

# 6. Salvar lista de itens que precisam re-download
all_need = need_download + has_cue_no_rom
if all_need:
    NEED_REDOWNLOAD.write_text(json.dumps(all_need, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nSalvo em: {NEED_REDOWNLOAD}")

    # Mostrar amostras
    print(f"\n=== AMOSTRAS (precisam re-download) ===")
    for item in all_need[:15]:
        print(f"  {item.get('serial', '?'):>12} | {item.get('name', '?')[:50]}")

# 7. Itens com BIN mas sem CHD - precisam de conversao, nao download
if has_rom_no_chd:
    print(f"\n=== AMOSTRAS (tem BIN mas sem CHD - precisa converter) ===")
    for item in has_rom_no_chd[:10]:
        print(f"  {item.get('serial', '?'):>12} | {item.get('name', '?')[:50]}")
