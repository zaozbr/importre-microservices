#!/usr/bin/env python3
"""Checa CUEs sem BIN em lotes de 5. Salva progresso em _cue_check_progress.json.
Uso: python _fix_cues_sem_bin_v3.py [--batch 5]
"""
import sys, re, json, shutil, time, argparse
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")
PROGRESS_FILE = PSX / "_cue_check_progress.json"

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

def normalize_stem(stem):
    return re.sub(r'[^a-z0-9]', '', stem.lower())

def load_progress():
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))
    return {"done": [], "stats": {"found_local": 0, "found_in_dup": 0, "truly_no_bin": 0, "moved_to_dup": 0, "added_to_importre": 0}}

def save_progress(p):
    PROGRESS_FILE.write_text(json.dumps(p, indent=2), encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=int, default=5)
    parser.add_argument('--rebuild', action='store_true', help='Reconstruir lista de CUEs')
    args = parser.parse_args()

    t0 = time.time()
    progress = load_progress()
    done_set = set(progress["done"])

    # Indexar CHDs por serial (rapido: apenas glob na raiz)
    chd_serials = set()
    for base in [PSX, DUP]:
        if not base.exists(): continue
        for c in base.glob("*.chd"):
            m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
            if m: chd_serials.add(m.group(1).upper())

    # Indexar BINs em dup (apenas raiz)
    dup_bins_by_name = {}
    dup_bins_by_stem = {}
    dup_bins_by_serial = {}
    if DUP.exists():
        for f in DUP.iterdir():
            if f.is_file() and f.suffix.lower() in {'.bin', '.img', '.iso'}:
                dup_bins_by_name[f.name.lower()] = f
                dup_bins_by_stem[normalize_stem(f.stem)] = f
                s = extract_serial(f.name)
                if s: dup_bins_by_serial.setdefault(s, []).append(f)

    # Coletar CUEs pendentes (apenas raiz de psx/ e dup/)
    pending = []
    for cue in PSX.glob("*.cue"):
        if str(cue) in done_set: continue
        serial = extract_serial(cue.stem)
        if serial and serial in chd_serials:
            progress["done"].append(str(cue))
            continue
        pending.append((cue, serial, "psx"))
    if DUP.exists():
        for cue in DUP.glob("*.cue"):
            if str(cue) in done_set: continue
            serial = extract_serial(cue.stem)
            if serial and serial in chd_serials:
                progress["done"].append(str(cue))
                continue
            pending.append((cue, serial, "dup"))

    total_pending = len(pending)
    batch = pending[:args.batch]
    print(f"Total pendente: {total_pending} | Processando lote de {len(batch)}")

    def find_bin_in_dup(ref):
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

    importre_items = []
    for i, (cue, serial, location) in enumerate(batch):
        try:
            content = cue.read_text(encoding="utf-8", errors="replace")
        except Exception:
            progress["done"].append(str(cue))
            continue
        refs = re.findall(r'FILE\s+"([^"]+)"', content)
        if not refs:
            progress["done"].append(str(cue))
            continue

        missing = [r for r in refs if not (cue.parent / r).exists()]

        if not missing:
            progress["stats"]["found_local"] += 1
            progress["done"].append(str(cue))
            print(f"  [{i+1}/{len(batch)}] OK local: {cue.name[:50]}")
            continue

        # Procurar em dup
        all_found = True
        for ref in missing:
            found = find_bin_in_dup(ref)
            if found:
                dest = cue.parent / Path(ref).name
                if not dest.exists():
                    try: shutil.copy2(str(found), str(dest))
                    except: all_found = False
            else:
                all_found = False

        if all_found:
            progress["stats"]["found_in_dup"] += 1
            progress["done"].append(str(cue))
            print(f"  [{i+1}/{len(batch)}] BIN em dup: {cue.name[:50]}")
            continue

        # Sem BIN
        progress["stats"]["truly_no_bin"] += 1
        if location == "psx":
            dest_cue = DUP / cue.name
            if not dest_cue.exists():
                try:
                    shutil.move(str(cue), str(dest_cue))
                    progress["stats"]["moved_to_dup"] += 1
                except: pass
        if serial:
            importre_items.append({"serial": serial, "name": cue.stem})
        progress["done"].append(str(cue))
        print(f"  [{i+1}/{len(batch)}] SEM BIN: {cue.name[:50]}")

    # Adicionar na fila importre
    if importre_items:
        try:
            sys.path.insert(0, str(PSX))
            from importre import file_lock, file_unlock, load_json, save_json, QUEUE_PATH
            fl = file_lock()
            try:
                data = load_json(QUEUE_PATH, {})
                existing = set()
                for q in data.get("queue", []): existing.add(q.get("serial", "").upper())
                for k in data.get("in_progress", {}).keys(): existing.add(k.upper())
                for k in data.get("completed", {}).keys(): existing.add(k.upper())
                for k in data.get("failed", {}).keys(): existing.add(k.upper())
                for item in importre_items:
                    s = item["serial"]
                    if s in existing: continue
                    data["queue"].append({"serial": s, "name": item["name"], "region": "", "section": "", "type": "commercial", "_needs_search": True})
                    existing.add(s)
                    progress["stats"]["added_to_importre"] += 1
                data["total"] = len(data.get("queue",[])) + len(data.get("in_progress",{})) + len(data.get("completed",{})) + len(data.get("failed",{}))
                save_json(QUEUE_PATH, data)
            finally:
                file_unlock(fl)
        except Exception as e:
            print(f"  Erro importre: {e}")

    save_progress(progress)
    s = progress["stats"]
    elapsed = time.time() - t0
    print(f"\nLote concluido em {elapsed:.1f}s")
    print(f"Restam: {total_pending - len(batch)} | Acumulado: local={s['found_local']} dup={s['found_in_dup']} sem_bin={s['truly_no_bin']} movidos={s['moved_to_dup']} importre={s['added_to_importre']}")

if __name__ == "__main__":
    main()
