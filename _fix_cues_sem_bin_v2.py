#!/usr/bin/env python3
"""Versao simplificada e rapida: checa CUEs sem BIN apenas na raiz de psx/ e dup/.
Para cada CUE sem BIN:
1. Procura o BIN em D:\\roms\\duplicados (match por nome, stem, serial)
2. Se achar, copia para junto do CUE
3. Se nao achar, move o CUE para D:\\roms\\duplicados e adiciona na fila importre
"""
import sys, re, json, shutil, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

def normalize_stem(stem):
    return re.sub(r'[^a-z0-9]', '', stem.lower())

t0 = time.time()

# 1. Indexar CHDs por serial
chd_serials = set()
for base in [PSX, DUP]:
    if not base.exists():
        continue
    for c in base.glob("*.chd"):
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
        if m:
            chd_serials.add(m.group(1).upper())
print(f"CHDs: {len(chd_serials)} seriais unicos ({time.time()-t0:.1f}s)")

# 2. Indexar BINs em D:\roms\duplicados (apenas raiz, nao recursivo)
dup_bins_by_name = {}
dup_bins_by_stem = {}
dup_bins_by_serial = {}
if DUP.exists():
    for f in DUP.iterdir():
        if f.is_file() and f.suffix.lower() in {'.bin', '.img', '.iso'}:
            dup_bins_by_name[f.name.lower()] = f
            dup_bins_by_stem[normalize_stem(f.stem)] = f
            serial = extract_serial(f.name)
            if serial:
                dup_bins_by_serial.setdefault(serial, []).append(f)
print(f"BINs em D:\\roms\\duplicados: {len(dup_bins_by_name)} ({time.time()-t0:.1f}s)")

# 3. Coletar CUEs para checar (apenas raiz de psx/ e dup/, nao subpastas)
cues_to_check = []
for cue in PSX.glob("*.cue"):
    serial = extract_serial(cue.stem)
    if serial and serial in chd_serials:
        continue
    cues_to_check.append((cue, serial, "psx"))
if DUP.exists():
    for cue in DUP.glob("*.cue"):
        serial = extract_serial(cue.stem)
        if serial and serial in chd_serials:
            continue
        cues_to_check.append((cue, serial, "dup"))
print(f"CUEs sem CHD para checar: {len(cues_to_check)} ({time.time()-t0:.1f}s)")
print()

# 4. Checar cada CUE
found_local = 0
found_in_dup = 0
truly_no_bin = 0
moved_to_dup = 0
importre_items = []

def find_bin_in_dup(ref):
    """Procura BIN em dup por nome, stem normalizado ou serial."""
    ref_name = Path(ref).name
    ref_stem = normalize_stem(Path(ref).stem)
    ref_serial = extract_serial(ref)
    if ref_name.lower() in dup_bins_by_name:
        return dup_bins_by_name[ref_name.lower()]
    if ref_stem in dup_bins_by_stem:
        return dup_bins_by_stem[ref_stem]
    if ref_serial and ref_serial in dup_bins_by_serial:
        return dup_bins_by_serial[ref_serial][0]
    return None

for i, (cue, serial, location) in enumerate(cues_to_check):
    try:
        content = cue.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    if not refs:
        continue

    missing = []
    for ref in refs:
        if not (cue.parent / ref).exists():
            missing.append(ref)

    if not missing:
        found_local += 1
        continue

    # Procurar missing em dup
    all_found = True
    for ref in missing:
        found = find_bin_in_dup(ref)
        if found:
            dest = cue.parent / Path(ref).name
            if not dest.exists():
                try:
                    shutil.copy2(str(found), str(dest))
                except Exception:
                    all_found = False
        else:
            all_found = False

    if all_found:
        found_in_dup += 1
        if found_in_dup <= 15:
            print(f"  [{i+1}/{len(cues_to_check)}] BIN encontrado em dup: {cue.name[:55]}")
        continue

    # Realmente sem BIN
    truly_no_bin += 1
    # Mover CUE para dup se nao estiver la
    if location == "psx":
        dest_cue = DUP / cue.name
        if not dest_cue.exists():
            try:
                shutil.move(str(cue), str(dest_cue))
                moved_to_dup += 1
            except Exception:
                pass
    # Adicionar na fila importre
    if serial:
        importre_items.append({"serial": serial, "name": cue.stem})

# 5. Adicionar na fila importre
added = 0
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
                s = item["serial"]
                if s in existing:
                    continue
                data["queue"].append({
                    "serial": s, "name": item["name"],
                    "region": "", "section": "", "type": "commercial",
                    "_needs_search": True,
                })
                existing.add(s)
                added += 1
            data["total"] = len(data.get("queue", [])) + len(data.get("in_progress", {})) + len(data.get("completed", {})) + len(data.get("failed", {}))
            save_json(QUEUE_PATH, data)
        finally:
            file_unlock(fl)
    except Exception as e:
        print(f"  Erro importre: {e}")

elapsed = time.time() - t0
print(f"\n{'='*60}")
print(f"RESUMO ({elapsed:.1f}s)")
print(f"  CUEs checados:              {len(cues_to_check)}")
print(f"  BINs locais OK:             {found_local}")
print(f"  BINs encontrados em dup:    {found_in_dup}")
print(f"  Realmente sem BIN:          {truly_no_bin}")
print(f"  CUEs movidos p/ D:\\roms\\dup: {moved_to_dup}")
print(f"  Adicionados ao importre:    {added}")
print(f"{'='*60}")
