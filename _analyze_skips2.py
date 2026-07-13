#!/usr/bin/env python3
"""Analisa os 671 skips: itens da lista de faltantes que o importre pulou porque
encontrou arquivos na pasta. Agora que BINs estao sendo apagados, quais precisam re-download?"""
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

# 1. Carregar lista de faltantes
print("Carregando lista de faltantes...")
missing_items = []
if MISSING_FILE.exists():
    for line in MISSING_FILE.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('|--') or line.startswith('|---'):
            continue
        # Formato markdown: | # | Serial | Nome |
        if line.startswith('|'):
            parts = [p.strip() for p in line.split('|')]
            # parts[0] = vazio, parts[1] = #, parts[2] = serial, parts[3] = nome
            if len(parts) >= 4:
                serial = parts[2]
                name = parts[3]
                if serial and serial != 'Serial':
                    missing_items.append({'serial': serial, 'name': name, 'region': ''})

print(f"Total na lista de faltantes: {len(missing_items)}")

# 2. Carregar fila atual
print("Carregando fila do importre...")
data = json.loads(QUEUE_FILE.read_text(encoding='utf-8'))
all_in_queue = set()
for item in data.get('queue', []):
    s = item.get('serial', '')
    if s:
        all_in_queue.add(s.upper())
for k in data.get('in_progress', {}).keys():
    all_in_queue.add(k.upper())
for k in data.get('completed', {}).keys():
    all_in_queue.add(k.upper())
for k in data.get('failed', {}).keys():
    all_in_queue.add(k.upper())

print(f"  Itens na fila (todos status): {len(all_in_queue)}")

# 3. Skips = itens da lista que NAO estao na fila
skip_items = []
for item in missing_items:
    serial = item.get('serial', '').upper()
    if serial and serial not in all_in_queue:
        skip_items.append(item)

print(f"  Skips (na lista mas nao na fila): {len(skip_items)}")

# 4. Indexar arquivos da colecao por serial
print("Indexando arquivos da colecao...")
chd_serials = set()
rom_serials = set()

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

print(f"  CHDs (por serial): {len(chd_serials)}")
print(f"  ROMs sem CHD (por serial): {len(rom_serials)}")

# 5. Categorizar skips
has_chd = []
has_rom_no_chd = []
need_download = []

for item in skip_items:
    serial = item.get('serial', '').upper()
    if serial in chd_serials:
        has_chd.append(item)
    elif serial in rom_serials:
        has_rom_no_chd.append(item)
    else:
        need_download.append(item)

print(f"\n=== ANALISE DOS {len(skip_items)} SKIPS ===")
print(f"  Tem CHD (skip correto):         {len(has_chd)}")
print(f"  Tem BIN/IMG mas sem CHD:        {len(has_rom_no_chd)}")
print(f"  Nao tem nada (precisa download): {len(need_download)}")

# 6. Salvar lista de itens que precisam re-download
if need_download:
    NEED_REDOWNLOAD.write_text(json.dumps(need_download, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nItens que precisam re-download salvos em: {NEED_REDOWNLOAD}")
    print(f"\n=== AMOSTRAS (precisam re-download) ===")
    for item in need_download[:20]:
        print(f"  {item.get('serial', '?'):>12} | {item.get('name', '?')[:50]}")

if has_rom_no_chd:
    print(f"\n=== AMOSTRAS (tem BIN mas sem CHD - converter) ===")
    for item in has_rom_no_chd[:10]:
        print(f"  {item.get('serial', '?'):>12} | {item.get('name', '?')[:50]}")

# 7. Para itens que precisam re-download: criar diretorio destino e adicionar na fila
if need_download:
    print(f"\n=== REAPLICANDO {len(need_download)} ITENS NA FILA DO IMPORTRE ===")
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Diretorio destino criado: {DEST_DIR}")

    # Adicionar itens na fila do importre
    fl = None
    try:
        # Usar file lock do importre
        sys.path.insert(0, str(Path(r"D:\roms\library\roms\psx")))
        from importre import file_lock, file_unlock, load_json, save_json, QUEUE_PATH
        fl = file_lock()
        data = load_json(QUEUE_PATH, {})
        added = 0
        for item in need_download:
            serial = item.get('serial', '')
            if not serial:
                continue
            # Verificar se ja esta na fila
            already = False
            for q in data.get('queue', []):
                if q.get('serial', '').upper() == serial.upper():
                    already = True
                    break
            if serial.upper() in {k.upper() for k in data.get('in_progress', {}).keys()}:
                already = True
            if serial.upper() in {k.upper() for k in data.get('completed', {}).keys()}:
                already = True
            if serial.upper() in {k.upper() for k in data.get('failed', {}).keys()}:
                already = True
            if not already:
                data['queue'].append({
                    'serial': serial,
                    'name': item.get('name', ''),
                    'region': item.get('region', ''),
                    'section': '',
                    'type': 'commercial',
                    '_needs_search': True
                })
                added += 1
        data['total'] = len(data.get('queue', [])) + len(data.get('in_progress', {})) + len(data.get('completed', {})) + len(data.get('failed', {}))
        save_json(QUEUE_PATH, data)
        print(f"  {added} itens adicionados a fila do importre!")
        print(f"  Nova fila: {len(data.get('queue', []))} pendentes")
    except Exception as e:
        print(f"  Erro ao adicionar na fila: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if fl:
            try:
                file_unlock(fl)
            except Exception:
                pass
