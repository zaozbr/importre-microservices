#!/usr/bin/env python3
"""Gera CUE para BINs standalone e move has_chd/track_2plus orfaos para D:\\roms\\duplicados.

Para standalone BINs:
- Se o BIN tem "Track 1" no nome, verifica se existem Track 2, 3, etc e gera CUE multi-track
- Se o BIN e unico (sem Track no nome), gera CUE single-track
- CUE gerado: MODE2/2352 para PSX

Para has_chd BINs:
- Move para D:\\roms\\duplicados (ja tem CHD)

Para track_2plus orfaos (sem CUE que os referencia):
- Move para D:\\roms\\duplicados
"""
import sys, re, json, shutil, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

data = json.loads((PSX / "_bins_analysis.json").read_text(encoding="utf-8"))

# ============================================================
# 1. GERAR CUEs PARA STANDALONE BINS
# ============================================================
print("=== GERANDO CUEs PARA BINS STANDALONE ===")
cues_generated = 0
cues_multi = 0
errors = 0

# Agrupar standalone por diretorio para detectar multi-track
standalone = data["standalone"]
# Group by parent dir + base name (without Track suffix)
from collections import defaultdict
groups = defaultdict(list)
for item in standalone:
    p = Path(item["path"])
    parent = str(p.parent)
    # Remove Track X suffix to get base name
    base = re.sub(r'\s*\(Track\s*\d+\)\s*$', '', p.stem, flags=re.I)
    base = re.sub(r'\s*\(Track\s*0?1\)\s*$', '', base, flags=re.I)
    groups[(parent, base.lower())].append(item)

for (parent, base), items in groups.items():
    parent_path = Path(parent)
    if len(items) == 1:
        # Single BIN - gerar CUE simples
        item = items[0]
        bin_path = Path(item["path"])
        cue_path = bin_path.with_suffix(".cue")
        if cue_path.exists():
            continue
        # Detectar modo: se tamanho e multiplo de 2352, provavelmente MODE2/2352
        size = bin_path.stat().st_size
        mode = "MODE2/2352"  # PSX default
        cue_content = f'FILE "{bin_path.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
        try:
            cue_path.write_text(cue_content, encoding="utf-8")
            cues_generated += 1
            if cues_generated <= 10:
                print(f"  [single] {cue_path.name[:55]}")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERRO: {bin_path.name[:50]}: {e}")
    else:
        # Multi-track - ordenar por Track numero
        def track_num(name):
            m = re.search(r'Track\s*(\d+)', name, re.I)
            return int(m.group(1)) if m else 1
        items.sort(key=lambda x: track_num(x["stem"]))
        
        # Gerar CUE multi-track
        base_name = base
        # Use o primeiro item's parent para o CUE
        cue_name = items[0]["stem"]
        # Remove Track suffix from cue name
        cue_name = re.sub(r'\s*\(Track\s*\d+\)\s*$', '', cue_name, flags=re.I)
        cue_path = parent_path / f"{cue_name}.cue"
        if cue_path.exists():
            continue
        
        cue_lines = []
        for i, item in enumerate(items):
            bin_path = Path(item["path"])
            track_n = track_num(item["stem"])
            if track_n == 1:
                mode = "MODE2/2352"
            else:
                mode = "AUDIO"
            cue_lines.append(f'FILE "{bin_path.name}" BINARY')
            cue_lines.append(f'  TRACK {track_n:02d} {mode}')
            if track_n == 1:
                cue_lines.append(f'    INDEX 01 00:00:00')
            else:
                # PREGAP de 2 segundos para tracks de audio
                cue_lines.append(f'    INDEX 00 00:00:00')
                cue_lines.append(f'    INDEX 01 00:02:00')
        
        cue_content = "\n".join(cue_lines) + "\n"
        try:
            cue_path.write_text(cue_content, encoding="utf-8")
            cues_generated += 1
            cues_multi += 1
            if cues_multi <= 10:
                print(f"  [multi {len(items)} tracks] {cue_path.name[:55]}")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERRO multi: {cue_path.name[:50]}: {e}")

print(f"\nCUEs gerados: {cues_generated} ({cues_multi} multi-track, {cues_generated - cues_multi} single-track)")
print(f"Erros: {errors}")

# ============================================================
# 2. MOVER has_chd PARA D:\roms\duplicados
# ============================================================
print("\n=== MOVENDO BINS COM CHD EXISTENTE PARA D:\\roms\\duplicados ===")
moved_chd = 0
for item in data["has_chd"]:
    p = Path(item["path"])
    if not p.exists():
        continue
    dest = DUP / p.name
    if dest.exists():
        # Ja existe em dup, deletar origem
        try:
            p.unlink()
            moved_chd += 1
        except:
            pass
    else:
        try:
            shutil.move(str(p), str(dest))
            moved_chd += 1
        except:
            pass
print(f"BINS com CHD movidos/deletados: {moved_chd}")

# ============================================================
# 3. MOVER track_2plus ORFAOS PARA D:\roms\duplicados
# ============================================================
print("\n=== MOVENDO TRACK 2+ ORFAOS PARA D:\\roms\\duplicados ===")
# Track 2+ orfaos = nao referenciados por nenhum CUE
# Ja filtramos referenced_by_cue separadamente, mas vamos checar
moved_tracks = 0
cue_refs_all = set()
for base in [PSX, DUP]:
    if not base.exists(): continue
    for cue in base.glob("*.cue"):
        try:
            content = cue.read_text(encoding="utf-8", errors="replace")
            refs = re.findall(r'FILE\s+"([^"]+)"', content)
            for ref in refs:
                cue_refs_all.add(Path(ref).name.lower())
                cue_refs_all.add(Path(ref).stem.lower())
        except: pass

for item in data["track_2plus"]:
    p = Path(item["path"])
    if not p.exists():
        continue
    # Se referenciado por algum CUE, nao mover
    if p.name.lower() in cue_refs_all or p.stem.lower() in cue_refs_all:
        continue
    # Orfao - mover para dup
    dest = DUP / p.name
    if dest.exists():
        try:
            p.unlink()
            moved_tracks += 1
        except:
            pass
    else:
        try:
            shutil.move(str(p), str(dest))
            moved_tracks += 1
        except:
            pass
print(f"Track 2+ orfaos movidos/deletados: {moved_tracks}")

# ============================================================
# RESUMO
# ============================================================
print(f"\n{'='*60}")
print(f"RESUMO FINAL")
print(f"  CUEs gerados (single-track): {cues_generated - cues_multi}")
print(f"  CUEs gerados (multi-track):  {cues_multi}")
print(f"  Total CUEs gerados:          {cues_generated}")
print(f"  Erros:                       {errors}")
print(f"  BINS com CHD movidos:        {moved_chd}")
print(f"  Track 2+ orfaos movidos:     {moved_tracks}")
print(f"{'='*60}")
