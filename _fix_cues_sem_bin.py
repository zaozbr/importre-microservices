#!/usr/bin/env python3
"""Checa todos os CUEs sem BIN em toda a arvore PSX.
Para cada CUE sem BIN:
1. Procura o BIN em D:\\roms\\duplicados (match por nome exato, stem, serial)
2. Se achar o BIN, copia para junto do CUE (ou ajusta o CUE)
3. Se nao achar, move o CUE para D:\\roms\\duplicados e adiciona na fila importre
"""
import sys, re, json, shutil, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

def normalize_stem(stem):
    s = re.sub(r'[^a-z0-9]', '', stem.lower())
    return s

# Indexar CHDs por serial
chd_serials = set()
for base in [PSX, DUP]:
    if not base.exists():
        continue
    for c in base.glob("*.chd"):
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
        if m:
            chd_serials.add(m.group(1).upper())

# Indexar todos os BINs/IMGs/ISOs em D:\roms\duplicados por nome e stem normalizado
dup_bins_by_name = {}
dup_bins_by_stem = {}
dup_bins_by_serial = {}
if DUP.exists():
    for f in DUP.iterdir():
        if f.suffix.lower() in {'.bin', '.img', '.iso'}:
            dup_bins_by_name[f.name.lower()] = f
            dup_bins_by_stem[normalize_stem(f.stem)] = f
            serial = extract_serial(f.name)
            if serial:
                dup_bins_by_serial.setdefault(serial, []).append(f)

print(f"CHDs por serial: {len(chd_serials)}")
print(f"BINs em D:\\roms\\duplicados: {len(dup_bins_by_name)}")
print()

# Escanear todos os CUEs
cues_to_check = []
for base in [PSX, DUP]:
    if not base.exists():
        continue
    for cue in base.rglob("*.cue"):
        serial = extract_serial(cue.stem)
        if serial and serial in chd_serials:
            continue  # ja tem CHD
        cues_to_check.append((cue, serial))

print(f"Total CUEs sem CHD para checar: {len(cues_to_check)}")

found_bin_in_dup = 0
found_bin_local = 0
truly_no_bin = 0
moved_to_dup = 0
added_to_importre = 0
importre_items = []

for i, (cue, serial) in enumerate(cues_to_check):
    content = cue.read_text(encoding="utf-8", errors="replace")
    refs = re.findall(r'FILE\s+"([^"]+)"', content)

    has_bin_local = False
    missing_refs = []
    for ref in refs:
        bin_path = cue.parent / ref
        if bin_path.exists():
            has_bin_local = True
        else:
            missing_refs.append(ref)

    if has_bin_local and not missing_refs:
        # Todos os BINs existem localmente - nao precisa fazer nada
        found_bin_local += 1
        continue

    if has_bin_local and missing_refs:
        # Tem alguns BINs mas faltam outros - ainda assim pode converter parcial?
        # Vamos checar se os missing estao em dup
        all_found = True
        for ref in missing_refs:
            ref_name = Path(ref).name
            ref_stem = normalize_stem(Path(ref).stem)
            ref_serial = extract_serial(ref)
            found = None
            # Buscar por nome exato
            if ref_name.lower() in dup_bins_by_name:
                found = dup_bins_by_name[ref_name.lower()]
            # Buscar por stem normalizado
            elif ref_stem in dup_bins_by_stem:
                found = dup_bins_by_stem[ref_stem]
            # Buscar por serial
            elif ref_serial and ref_serial in dup_bins_by_serial:
                found = dup_bins_by_serial[ref_serial][0]
            if found:
                # Copiar BIN para junto do CUE
                dest = cue.parent / ref_name
                if not dest.exists():
                    try:
                        shutil.copy2(str(found), str(dest))
                        found_bin_in_dup += 1
                        print(f"  [{i+1}/{len(cues_to_check)}] BIN encontrado em dup: {found.name[:50]} -> {dest.parent.name}/")
                    except Exception as e:
                        all_found = False
                else:
                    found_bin_in_dup += 1
            else:
                all_found = False
        if not all_found:
            # Ainda faltam BINs - se o CUE esta em psx/, mover para dup
            if cue.parent != DUP and not cue.parent.is_relative_to(DUP):
                # Nao mover se tem pelo menos alguns BINs locais
                pass
        continue

    # CUE sem nenhum BIN local - procurar todos em dup
    all_found_in_dup = True
    for ref in refs:
        ref_name = Path(ref).name
        ref_stem = normalize_stem(Path(ref).stem)
        ref_serial = extract_serial(ref)
        found = None
        if ref_name.lower() in dup_bins_by_name:
            found = dup_bins_by_name[ref_name.lower()]
        elif ref_stem in dup_bins_by_stem:
            found = dup_bins_by_stem[ref_stem]
        elif ref_serial and ref_serial in dup_bins_by_serial:
            found = dup_bins_by_serial[ref_serial][0]
        if not found:
            all_found_in_dup = False
            break

    if all_found_in_dup and refs:
        # Copiar todos os BINs de dup para junto do CUE
        for ref in refs:
            ref_name = Path(ref).name
            ref_stem = normalize_stem(Path(ref).stem)
            ref_serial = extract_serial(ref)
            found = None
            if ref_name.lower() in dup_bins_by_name:
                found = dup_bins_by_name[ref_name.lower()]
            elif ref_stem in dup_bins_by_stem:
                found = dup_bins_by_stem[ref_stem]
            elif ref_serial and ref_serial in dup_bins_by_serial:
                found = dup_bins_by_serial[ref_serial][0]
            if found:
                dest = cue.parent / ref_name
                if not dest.exists():
                    try:
                        shutil.copy2(str(found), str(dest))
                    except Exception:
                        pass
        found_bin_in_dup += 1
        print(f"  [{i+1}/{len(cues_to_check)}] CUE completo em dup: {cue.name[:50]}")
        continue

    # Realmente nao tem BIN em lugar nenhum
    truly_no_bin += 1
    # Mover CUE para D:\roms\duplicados (se ja nao estiver la)
    if cue.parent != DUP:
        dest_cue = DUP / cue.name
        if not dest_cue.exists():
            try:
                shutil.move(str(cue), str(dest_cue))
                moved_to_dup += 1
            except Exception as e:
                pass
    # Adicionar na fila do importre
    if serial:
        importre_items.append({
            "serial": serial,
            "name": cue.stem,
            "cue": cue.name,
        })

# Adicionar na fila do importre
if importre_items:
    print(f"\nAdicionando {len(importre_items)} itens na fila do importre...")
    try:
        sys.path.insert(0, str(PSX))
        from importre import file_lock, file_unlock, load_json, save_json, QUEUE_PATH
        fl = file_lock()
        try:
            data = load_json(QUEUE_PATH, {})
            existing = set()
            for q in data.get("queue", []):
                existing.add(q.get("serial", "").upper())
            for k in data.get("in_progress", {}).keys():
                existing.add(k.upper())
            for k in data.get("completed", {}).keys():
                existing.add(k.upper())
            for k in data.get("failed", {}).keys():
                existing.add(k.upper())
            for item in importre_items:
                serial = item["serial"]
                if serial in existing:
                    continue
                data["queue"].append({
                    "serial": serial,
                    "name": item["name"],
                    "region": "",
                    "section": "",
                    "type": "commercial",
                    "_needs_search": True,
                })
                existing.add(serial)
                added_to_importre += 1
            data["total"] = len(data.get("queue", [])) + len(data.get("in_progress", {})) + len(data.get("completed", {})) + len(data.get("failed", {}))
            save_json(QUEUE_PATH, data)
        finally:
            file_unlock(fl)
    except Exception as e:
        print(f"  Erro: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'='*60}")
print(f"RESUMO")
print(f"  CUEs checados:                    {len(cues_to_check)}")
print(f"  BINs locais OK:                   {found_bin_local}")
print(f"  BINs encontrados em dup:          {found_bin_in_dup}")
print(f"  Realmente sem BIN:                {truly_no_bin}")
print(f"  CUEs movidos para D:\\roms\\dup:   {moved_to_dup}")
print(f"  Itens adicionados ao importre:    {added_to_importre}")
print(f"{'='*60}")
