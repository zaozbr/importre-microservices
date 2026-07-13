#!/usr/bin/env python3
"""Identifica CUEs sem BIN em D:\\roms\\duplicados e adiciona na fila do importre."""
import sys, re, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

DUP = Path(r"D:\roms\duplicados")
PSX = Path(r"D:\roms\library\roms\psx")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# Indexar CHDs por serial
chd_serials = set()
for c in PSX.glob("*.chd"):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
    if m:
        chd_serials.add(m.group(1).upper())
for c in DUP.glob("*.chd"):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
    if m:
        chd_serials.add(m.group(1).upper())

print(f"CHDs por serial: {len(chd_serials)}")

# Encontrar CUEs sem BIN em D:\roms\duplicados
need_download = []
cues_no_bin = 0
cues_with_serial = 0

for cue in DUP.glob("*.cue"):
    serial = extract_serial(cue.stem)
    if serial and serial in chd_serials:
        continue  # ja tem CHD
    content = cue.read_text(encoding="utf-8", errors="replace")
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    has_bin = False
    for ref in refs:
        bin_path = cue.parent / ref
        if bin_path.exists():
            has_bin = True
            break
    if not has_bin:
        cues_no_bin += 1
        if serial:
            cues_with_serial += 1
            need_download.append({
                "serial": serial,
                "name": cue.stem,
                "cue": cue.name,
            })

print(f"CUEs sem BIN em D:\\roms\\duplicados: {cues_no_bin}")
print(f"  Com serial: {cues_with_serial}")
print(f"  Sem serial: {cues_no_bin - cues_with_serial}")

# Mostrar amostras
print(f"\nAmostras (com serial):")
for item in need_download[:15]:
    print(f"  {item['serial']:>12} | {item['name'][:50]}")

# Adicionar na fila do importre
if need_download:
    print(f"\nAdicionando {len(need_download)} itens na fila do importre...")
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

            added = 0
            for item in need_download:
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
                added += 1
            data["total"] = len(data.get("queue", [])) + len(data.get("in_progress", {})) + len(data.get("completed", {})) + len(data.get("failed", {}))
            save_json(QUEUE_PATH, data)
            print(f"  {added} itens adicionados na fila do importre!")
            print(f"  Fila agora: {len(data.get('queue', []))} pendentes")
        finally:
            file_unlock(fl)
    except Exception as e:
        print(f"  Erro: {e}")
        import traceback
        traceback.print_exc()
else:
    print("Nenhum item para adicionar na fila.")
