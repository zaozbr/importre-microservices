#!/usr/bin/env python3
"""Converte todos os .cue em psx/ (raiz e subpastas) para .chd.
Se a conversao for bem-sucedida e o CHD nao existia antes, move a fonte para D:\roms\duplicados."""
import subprocess, shutil, sys, re, time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")
F = Path(r"F:\chd_temp")
F.mkdir(exist_ok=True)
DUP = Path(r"D:\roms\duplicados")
DUP.mkdir(exist_ok=True)
CHDMAN = PSX / "chdman.exe"

def extract_serial(name):
    m = re.search(r"([A-Z]{2,4}[-]\d{3,5})", name, re.I)
    return m.group(1).upper() if m else None

def sanitize(name):
    for c in '<>:"/\\|?*':
        name = name.replace(c, "")
    if len(name) > 180: name = name[:180]
    return name.strip().rstrip(".")

def build_chd_name(cue_path):
    stem = cue_path.stem
    serial = extract_serial(stem)
    base = re.sub(r"\(Track \d+\)", "", stem, flags=re.I).strip()
    base = re.sub(r"\(Disc \d+\)", "", base, flags=re.I).strip()
    base = re.sub(r"\(.*?\)", "", base).strip()
    base = re.sub(r"[^\w\s-]", "", base)
    base = re.sub(r"\s+", "-", base)
    base = re.sub(r"-+", "-", base).strip("-")
    if serial:
        base = f"{base}-{serial}"
    return sanitize(base) + ".chd"

# CHDs existentes
existing_chds = {f.stem.lower() for f in PSX.glob("*.chd")}
existing_chds |= {f.stem.lower().replace("_", "-") for f in PSX.glob("*.chd")}

# Encontrar todos os CUEs
cues = []
for cue in PSX.rglob("*.cue"):
    if "nao-conversivel" in cue.name.lower():
        continue
    cues.append(cue)

print(f"CUEs encontrados: {len(cues)}")

ok = 0
fail = 0
skip = 0
moved = 0

for i, cue in enumerate(cues):
    chd_name = build_chd_name(cue)
    chd_dst = PSX / chd_name

    # Verificar se BIN existe
    try:
        content = cue.read_text(encoding="utf-8", errors="replace")
    except:
        continue
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    if not refs:
        continue
    has_bin = all((cue.parent / r).exists() for r in refs)
    if not has_bin:
        # Tentar encontrar BINs em outras pastas
        for ref in refs:
            ref_name = Path(ref).name
            if not (cue.parent / ref).exists():
                # Buscar em psx/
                for f in PSX.rglob(ref_name):
                    if f != cue.parent / ref:
                        shutil.copy2(str(f), str(cue.parent / ref_name))
                        break
        has_bin = all((cue.parent / r).exists() for r in refs)
    if not has_bin:
        print(f"  [{i+1}/{len(cues)}] SEM BIN: {cue.name[:50]}")
        skip += 1
        continue

    # Ja tem CHD?
    if chd_dst.exists() and chd_dst.stat().st_size > 1024 * 1024:
        print(f"  [{i+1}/{len(cues)}] JA EXISTE: {chd_name[:50]} ({chd_dst.stat().st_size//1024}KB)")
        skip += 1
        # Mover fonte para dup
        for ref in refs:
            binf = cue.parent / ref
            if binf.exists():
                d = DUP / binf.name
                if not d.exists():
                    try: shutil.move(str(binf), str(d))
                    except: pass
        d = DUP / cue.name
        if not d.exists():
            try: shutil.move(str(cue), str(d))
            except: pass
        moved += 1
        continue

    print(f"  [{i+1}/{len(cues)}] Convertendo: {cue.name[:50]} -> {chd_name[:40]}")

    # Copiar BINs e CUE para F: (SSD)
    worker_id = i % 100
    temp_files = []
    temp_cue = F / f"_batch_{worker_id}.cue"
    new_content = content
    for ref in refs:
        src = cue.parent / ref
        if src.exists():
            dst_bin = F / f"_batch_{worker_id}_{Path(ref).name}"
            shutil.copy2(str(src), str(dst_bin))
            temp_files.append(dst_bin)
            new_content = new_content.replace(ref, dst_bin.name)
    temp_cue.write_text(new_content, encoding="utf-8")
    temp_files.append(temp_cue)

    chd_tmp = F / chd_name
    if chd_tmp.exists(): chd_tmp.unlink()

    try:
        r = subprocess.run([str(CHDMAN), "createcd", "-i", str(temp_cue), "-o", str(chd_tmp), "-f"],
                           capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        r = None

    success = chd_tmp.exists() and chd_tmp.stat().st_size > 1024 * 1024

    if success:
        # Mover CHD para psx/
        try:
            if chd_dst.exists(): chd_dst.unlink()
        except:
            print(f"    AVISO: nao foi possivel remover CHD existente, pulando")
            chd_tmp.unlink(missing_ok=True)
            continue
        shutil.move(str(chd_tmp), str(chd_dst))
        print(f"    OK: {chd_name} ({chd_dst.stat().st_size//1024}KB)")
        ok += 1
        # Mover fonte para dup
        for ref in refs:
            binf = cue.parent / ref
            if binf.exists():
                d = DUP / binf.name
                if not d.exists():
                    try: shutil.move(str(binf), str(d))
                    except: pass
        d = DUP / cue.name
        if not d.exists():
            try: shutil.move(str(cue), str(d))
            except: pass
        moved += 1
    else:
        print(f"    FALHA: {r.stderr[:150] if r and r.stderr else 'sem output'}")
        fail += 1
        if chd_tmp.exists(): chd_tmp.unlink(missing_ok=True)

    # Limpar temp
    for tf in temp_files:
        try: tf.unlink()
        except: pass

print(f"\n=== RESUMO ===")
print(f"OK: {ok} | Falhas: {fail} | Pulados: {skip} | Fontes movidas: {moved}")
