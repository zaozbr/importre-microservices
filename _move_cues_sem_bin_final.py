#!/usr/bin/env python3
"""1. Move CUEs sem BIN de psx/ para D:\roms\duplicados
2. Readiciona seriais à fila do importre
3. Corrige _collection_overview.py para ignorar D:\roms\duplicados
"""
import sys, re, json, shutil
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# 1. Encontrar CUEs sem BIN em psx/ (apenas raiz, nao dup)
cues_sem_bin = []
for cue in PSX.glob("*.cue"):
    try:
        content = cue.read_text(encoding="utf-8", errors="replace")
    except:
        continue
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    if not refs:
        continue
    has_bin = any((cue.parent / r).exists() for r in refs)
    if not has_bin:
        serial = extract_serial(cue.stem)
        cues_sem_bin.append((cue, serial, cue.stem))

print(f"CUEs sem BIN em psx/: {len(cues_sem_bin)}")

# 2. Mover para D:\roms\duplicados
moved = 0
for cue, serial, stem in cues_sem_bin:
    dest = DUP / cue.name
    if dest.exists():
        # Ja existe em dup, deletar origem
        try:
            cue.unlink()
            moved += 1
        except:
            pass
    else:
        try:
            shutil.move(str(cue), str(dest))
            moved += 1
        except:
            pass
print(f"CUEs movidos para D:\\roms\\duplicados: {moved}")

# 3. Readicionar à fila do importre
added = 0
added_no_serial = 0
if cues_sem_bin:
    try:
        sys.path.insert(0, str(PSX))
        from importre import file_lock, file_unlock, load_json, save_json, QUEUE_PATH
        fl = file_lock()
        try:
            data = load_json(QUEUE_PATH, {})
            existing = set()
            existing_names = set()
            for q in data.get("queue", []):
                if q.get("serial"): existing.add(q["serial"].upper())
                if q.get("name"): existing_names.add(q["name"].lower().strip())
            for k in data.get("in_progress", {}).keys(): existing.add(k.upper())
            for k in data.get("completed", {}).keys(): existing.add(k.upper())
            for k in data.get("failed", {}).keys(): existing.add(k.upper())

            for cue, serial, stem in cues_sem_bin:
                if serial:
                    if serial in existing: continue
                    data["queue"].append({
                        "serial": serial, "name": stem,
                        "region": "", "section": "", "type": "commercial",
                        "_needs_search": True,
                    })
                    existing.add(serial)
                    added += 1
                else:
                    if stem.lower().strip() in existing_names: continue
                    data["queue"].append({
                        "serial": "", "name": stem,
                        "region": "", "section": "", "type": "commercial",
                        "_needs_search": True, "_no_serial": True, "_search_by_name": True,
                    })
                    existing_names.add(stem.lower().strip())
                    added_no_serial += 1
            data["total"] = len(data.get("queue",[])) + len(data.get("in_progress",{})) + len(data.get("completed",{})) + len(data.get("failed",{}))
            save_json(QUEUE_PATH, data)
        finally:
            file_unlock(fl)
    except Exception as e:
        print(f"Erro importre: {e}")
        import traceback
        traceback.print_exc()

print(f"Adicionados ao importre COM serial: {added}")
print(f"Adicionados ao importre SEM serial: {added_no_serial}")
