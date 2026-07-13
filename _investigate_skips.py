#!/usr/bin/env python3
"""Investiga skips do importre - identifica jogos que existem na pasta mas podem precisar de re-download."""
import sys, json, re, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = PSX / "duplicados"
STATE = Path(r"D:\roms\library\roms\_importre_state")
QUEUE_FILE = STATE / "queue.json"
SKIP_FILE = STATE / "skip_list.json"

# 1. Carregar fila do importre
queue = []
if QUEUE_FILE.exists():
    try:
        queue = json.loads(QUEUE_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"Erro lendo queue.json: {e}")

# 2. Carregar skip list
skips = []
if SKIP_FILE.exists():
    try:
        skips = json.loads(SKIP_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"Erro lendo skip_list.json: {e}")

# 3. Analisar itens da fila por status
status_counts = {}
for item in queue:
    s = item.get('status', 'unknown')
    status_counts[s] = status_counts.get(s, 0) + 1
print(f"=== FILA IMPORTRE ===")
print(f"Total itens: {len(queue)}")
for s, c in sorted(status_counts.items(), key=lambda x: -x[1]):
    print(f"  {s}: {c}")

# 4. Itens skipped - por que?
skipped_items = [item for item in queue if item.get('status') == 'skipped']
print(f"\n=== ITENS SKIPPED: {len(skipped_items)} ===")

# 5. Verificar se itens skipped tem CHD ou BIN na pasta
chd_files = set()
for c in PSX.glob("*.chd"):
    chd_files.add(c.stem.lower())
if DUP.exists():
    for c in DUP.glob("*.chd"):
        chd_files.add(c.stem.lower())

bin_files = set()
for f in PSX.glob("*.bin"):
    bin_files.add(f.stem.lower())
for f in PSX.glob("*.img"):
    bin_files.add(f.stem.lower())
if DUP.exists():
    for f in DUP.glob("*.bin"):
        bin_files.add(f.stem.lower())
    for f in DUP.glob("*.img"):
        bin_files.add(f.stem.lower())

cue_files = set()
for f in PSX.glob("*.cue"):
    cue_files.add(f.stem.lower())
if DUP.exists():
    for f in DUP.glob("*.cue"):
        cue_files.add(f.stem.lower())

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# 6. Categorizar skips
has_chd = 0
has_bin_no_chd = 0
has_cue_no_bin = 0
nothing = 0
skip_samples = []

for item in skipped_items[:50]:
    title = item.get('title', item.get('name', ''))
    serial = item.get('serial', extract_serial(title))
    # Procurar por serial nos arquivos
    found_chd = False
    found_bin = False
    found_cue = False
    if serial:
        for cn in chd_files:
            if serial.lower() in cn:
                found_chd = True
                break
        for bn in bin_files:
            if serial.lower() in bn:
                found_bin = True
                break
        for cun in cue_files:
            if serial.lower() in cun:
                found_cue = True
                break

    if found_chd:
        has_chd += 1
    elif found_bin:
        has_bin_no_chd += 1
    elif found_cue:
        has_cue_no_bin += 1
    else:
        nothing += 1

    if len(skip_samples) < 10:
        skip_samples.append({
            'title': title[:50],
            'serial': serial,
            'has_chd': found_chd,
            'has_bin': found_bin,
            'has_cue': found_cue,
            'skip_reason': item.get('skip_reason', item.get('reason', ''))
        })

print(f"\n=== ANALISE DOS SKIPS (primeiros 50) ===")
print(f"  Tem CHD (skip correto):     {has_chd}")
print(f"  Tem BIN mas sem CHD:        {has_bin_no_chd}")
print(f"  Tem CUE mas sem BIN:        {has_cue_no_bin}")
print(f"  Nao tem nada (precisa baixar): {nothing}")

print(f"\n=== AMOSTRAS ===")
for s in skip_samples:
    print(f"  {s['serial'] or '?':>12} | CHD={s['has_chd']} BIN={s['has_bin']} CUE={s['has_cue']} | {s['skip_reason'][:30]} | {s['title']}")

# 7. Verificar todos os skips
print(f"\n=== ANALISE COMPLETA DOS SKIPS ===")
has_chd_all = 0
has_bin_no_chd_all = 0
has_cue_no_bin_all = 0
nothing_all = 0
need_redownload = []

for item in skipped_items:
    title = item.get('title', item.get('name', ''))
    serial = item.get('serial', extract_serial(title))
    found_chd = False
    found_bin = False
    found_cue = False
    if serial:
        for cn in chd_files:
            if serial.lower() in cn:
                found_chd = True
                break
        for bn in bin_files:
            if serial.lower() in bn:
                found_bin = True
                break
        for cun in cue_files:
            if serial.lower() in cun:
                found_cue = True
                break

    if found_chd:
        has_chd_all += 1
    elif found_bin:
        has_bin_no_chd_all += 1
        need_redownload.append(item)
    elif found_cue:
        has_cue_no_bin_all += 1
        need_redownload.append(item)
    else:
        nothing_all += 1
        need_redownload.append(item)

print(f"  Total skips: {len(skipped_items)}")
print(f"  Tem CHD (skip correto):       {has_chd_all}")
print(f"  Tem BIN mas sem CHD:          {has_bin_no_chd_all}")
print(f"  Tem CUE mas sem BIN:          {has_cue_no_bin_all}")
print(f"  Nao tem nada (precisa baixar): {nothing_all}")
print(f"  TOTAL precisam re-download:   {len(need_redownload)}")

# 8. Salvar lista de itens que precisam re-download
if need_redownload:
    out = Path(r"D:\roms\library\roms\psx\_need_redownload.json")
    out.write_text(json.dumps(need_redownload, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n  Salvo em: {out}")
