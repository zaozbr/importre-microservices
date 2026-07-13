#!/usr/bin/env python3
"""Move CUEs sem BIN e todos os duplicados de psx/duplicados para D:\\rom\\duplicados.
Tambem identifica jogos que precisam re-download e adiciona na fila do importre."""
import sys, re, json, shutil, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
OLD_DUP = PSX / "duplicados"
NEW_DUP = Path(r"D:\roms\duplicados")
QUEUE_FILE = Path(r"D:\roms\library\roms\_importre_state\queue.json")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# 1. Criar pasta destino
NEW_DUP.mkdir(parents=True, exist_ok=True)
print(f"Pasta destino: {NEW_DUP}")

# 2. Mover tudo de psx/duplicados para D:\rom\duplicados
moved_from_dup = 0
if OLD_DUP.exists():
    print(f"\nMovendo psx/duplicados -> D:\\rom\\duplicados...")
    for f in OLD_DUP.iterdir():
        if not f.is_file():
            continue
        dst = NEW_DUP / f.name
        if dst.exists():
            # Ja existe, pular
            continue
        try:
            shutil.move(str(f), str(dst))
            moved_from_dup += 1
        except Exception as e:
            print(f"  ERRO: {f.name}: {e}")
    print(f"  {moved_from_dup} arquivos movidos de psx/duplicados")

# 3. Mover CUEs sem BIN da pasta principal para D:\rom\duplicados
moved_cues = 0
moved_bins_no_chd = 0
need_download = []

# Indexar CHDs por serial
chd_serials = set()
for c in PSX.glob("*.chd"):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
    if m:
        chd_serials.add(m.group(1).upper())

print(f"\nMovendo CUEs sem BIN da pasta principal...")
for cue in PSX.glob("*.cue"):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', cue.stem, re.I)
    serial = m.group(1).upper() if m else None
    if serial and serial in chd_serials:
        continue  # ja tem CHD
    # Verificar se BIN existe
    content = cue.read_text(encoding="utf-8", errors="replace")
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    has_bin = False
    for ref in refs:
        bin_path = cue.parent / ref
        if bin_path.exists():
            has_bin = True
            break
    if not has_bin:
        # Mover CUE para D:\rom\duplicados
        dst = NEW_DUP / cue.name
        if not dst.exists():
            try:
                shutil.move(str(cue), str(dst))
                moved_cues += 1
            except Exception as e:
                print(f"  ERRO CUE: {cue.name}: {e}")
        # Adicionar na lista de re-download
        if serial:
            need_download.append({
                "serial": serial,
                "name": cue.stem,
                "cue": cue.name,
            })

print(f"  {moved_cues} CUEs sem BIN movidos")

# 4. Mover BINs/IMGs sem CUE e sem CHD para D:\rom\duplicados
print(f"\nMovendo BINs/IMGs sem CUE e sem CHD...")
for f in PSX.glob("*"):
    if f.suffix.lower() not in {".bin", ".img", ".iso"}:
        continue
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', f.stem, re.I)
    serial = m.group(1).upper() if m else None
    if serial and serial in chd_serials:
        continue  # ja tem CHD
    cue = f.with_suffix(".cue")
    if cue.exists():
        continue  # tem CUE, sera processado
    # Pular multi-track (so Track 1 ou sem track)
    if re.search(r'Track\s*[2-9]', f.stem, re.I):
        continue
    # Mover para D:\rom\duplicados
    dst = NEW_DUP / f.name
    if not dst.exists():
        try:
            shutil.move(str(f), str(dst))
            moved_bins_no_chd += 1
        except Exception as e:
            print(f"  ERRO BIN: {f.name}: {e}")

print(f"  {moved_bins_no_chd} BINs/IMGs movidos")

# 5. Mover ECMs sem CHD para D:\rom\duplicados
moved_ecms = 0
for f in PSX.glob("*.ecm"):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', f.stem, re.I)
    serial = m.group(1).upper() if m else None
    if serial and serial in chd_serials:
        continue
    dst = NEW_DUP / f.name
    if not dst.exists():
        try:
            shutil.move(str(f), str(dst))
            moved_ecms += 1
        except Exception as e:
            print(f"  ERRO ECM: {f.name}: {e}")
print(f"\n  {moved_ecms} ECMs movidos")

# 6. Relatorio
print(f"\n{'='*60}")
print(f"RESUMO DA MIGRACAO")
print(f"  De psx/duplicados:    {moved_from_dup} arquivos")
print(f"  CUEs sem BIN:         {moved_cues}")
print(f"  BINs/IMGs sem CUE:    {moved_bins_no_chd}")
print(f"  ECMs:                 {moved_ecms}")
print(f"  TOTAL movidos:        {moved_from_dup + moved_cues + moved_bins_no_chd + moved_ecms}")
print(f"  Precisam re-download: {len(need_download)}")
print(f"{'='*60}")

# 7. Adicionar na fila do importre
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

# 8. Verificar estado final
print(f"\n=== ESTADO FINAL ===")
psx_files = list(PSX.glob("*"))
chds = [f for f in psx_files if f.suffix == ".chd"]
bins = [f for f in psx_files if f.suffix.lower() in {".bin", ".img", ".iso"}]
cues = [f for f in psx_files if f.suffix == ".cue"]
ecms = [f for f in psx_files if f.suffix == ".ecm"]
print(f"  psx/: CHD={len(chds)} BIN={len(bins)} CUE={len(cues)} ECM={len(ecms)}")

dup_files = list(NEW_DUP.glob("*"))
dup_chds = [f for f in dup_files if f.suffix == ".chd"]
dup_bins = [f for f in dup_files if f.suffix.lower() in {".bin", ".img", ".iso"}]
dup_cues = [f for f in dup_files if f.suffix == ".cue"]
dup_ecms = [f for f in dup_files if f.suffix == ".ecm"]
print(f"  D:\\rom\\duplicados: CHD={len(dup_chds)} BIN={len(dup_bins)} CUE={len(dup_cues)} ECM={len(dup_ecms)}")
