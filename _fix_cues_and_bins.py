#!/usr/bin/env python3
"""Correcao completa:
1. Deleta BINs em dup/ que ja tem CHD
2. Restaura BINs em dup/ que pertencem a CUEs em psx/ (movidos por engano)
3. Regenera CUEs multi-track corretamente em psx/
4. Move BINs em dup/ que pertencem a CUEs em dup/ de volta para junto dos CUEs
"""
import sys, re, json, shutil, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from collections import defaultdict

PSX = Path(r"D:\roms\library\roms\psx")
DUP = Path(r"D:\roms\duplicados")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

def normalize_base(name):
    """Remove Track X, Disc X, (region) etc para agrupar tracks do mesmo jogo."""
    s = re.sub(r'\s*\(Track\s*\d+\)\s*$', '', name, flags=re.I)
    s = re.sub(r'\s*\(Track\s*0?(\d+)\)\s*$', '', s, flags=re.I)
    return s.strip().lower()

# ============================================================
# 0. Indexar CHDs por serial e stem
# ============================================================
print("Indexando CHDs...")
chd_serials = set()
chd_stems = set()
for base in [PSX, DUP]:
    if not base.exists(): continue
    for c in base.glob("*.chd"):
        chd_stems.add(c.stem.lower())
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
        if m: chd_serials.add(m.group(1).upper())
print(f"  {len(chd_serials)} seriais com CHD")

# ============================================================
# 1. DELETAR BINs em dup/ que ja tem CHD
# ============================================================
print("\n=== 1. DELETANDO BINS EM DUP/ COM CHD EXISTENTE ===")
deleted_chd = 0
bins_dup = list(DUP.glob("*.bin")) if DUP.exists() else []
for f in bins_dup:
    serial = extract_serial(f.stem)
    has_chd = False
    if serial and serial in chd_serials:
        has_chd = True
    elif f.stem.lower() in chd_stems:
        has_chd = True
    # Tambem checar por base name (sem Track)
    elif normalize_base(f.stem) in chd_stems:
        has_chd = True
    if has_chd:
        try:
            f.unlink()
            deleted_chd += 1
        except:
            pass
print(f"  {deleted_chd} BINs com CHD deletados de dup/")

# ============================================================
# 2. INDEXAR CUEs EXISTENTES E SEUS BINS REFERENCIADOS
# ============================================================
print("\n=== 2. INDEXANDO CUEs E BINS REFERENCIADOS ===")
# Para cada CUE, saber: diretorio, lista de BINs que referencia
cue_info = []  # [(cue_path, [bin_names])]
for base in [PSX, DUP]:
    if not base.exists(): continue
    for cue in base.glob("*.cue"):
        try:
            content = cue.read_text(encoding="utf-8", errors="replace")
            refs = re.findall(r'FILE\s+"([^"]+)"', content)
            cue_info.append((cue, refs))
        except:
            pass
print(f"  {len(cue_info)} CUEs indexados")

# Criar mapa: bin_name -> set de CUEs que o referenciam
bin_to_cues = defaultdict(list)
for cue, refs in cue_info:
    for ref in refs:
        bin_to_cues[Path(ref).name.lower()].append(cue)

# ============================================================
# 3. RESTAURAR BINs em dup/ QUE PERTENCEM A CUEs EM PSX/
# ============================================================
print("\n=== 3. RESTAURANDO BINS DE DUP/ PARA PSX/ (PERTENCEM A CUES EM PSX/) ===")
restored_to_psx = 0
bins_dup_remaining = list(DUP.glob("*.bin")) if DUP.exists() else []
for f in bins_dup_remaining:
    bin_name_lower = f.name.lower()
    # Este BIN e referenciado por algum CUE em psx/?
    for cue in bin_to_cues.get(bin_name_lower, []):
        if cue.parent == PSX:
            # Restaurar para psx/
            dest = PSX / f.name
            if not dest.exists():
                try:
                    shutil.move(str(f), str(dest))
                    restored_to_psx += 1
                except:
                    pass
            else:
                # Ja existe la, deletar de dup
                try:
                    f.unlink()
                    restored_to_psx += 1
                except:
                    pass
            break
print(f"  {restored_to_psx} BINs restaurados para psx/")

# ============================================================
# 4. RESTAURAR BINs em dup/ QUE PERTENCEM A CUEs EM DUP/
# ============================================================
print("\n=== 4. MOVENDO BINS DE DUP/ PARA JUNTO DE CUES EM DUP/ (se ja nao estao) ===")
# Ja estao em dup/, so garantir que estao na raiz (ja estao)
# Nada a fazer aqui - eles ja estao em dup/
print("  (BINs ja estao em dup/ com CUEs em dup/)")

# ============================================================
# 5. REGENERAR CUEs MULTI-TRACK CORRETAMENTE
# ============================================================
print("\n=== 5. REGENERANDO CUES MULTI-TRACK ===")

# Agrupar todos os BINs por (diretorio, base_name) para detectar multi-track
all_bins = defaultdict(list)  # (parent_str, base_lower) -> [bin_paths]
for base in [PSX, DUP]:
    if not base.exists(): continue
    for f in base.glob("*.bin"):
        parent = str(f.parent)
        base_name = normalize_base(f.stem)
        all_bins[(parent, base_name)].append(f)

cues_regenerated = 0
cues_created = 0

for (parent_str, base_lower), bins in all_bins.items():
    if len(bins) <= 1:
        continue  # single-track, ja tem CUE
    
    parent = Path(parent_str)
    
    # Ordenar por Track numero
    def track_num(name):
        m = re.search(r'Track\s*0*(\d+)', name, re.I)
        return int(m.group(1)) if m else 1
    bins.sort(key=lambda f: track_num(f.stem))
    
    # Nome do CUE: usar o base name sem Track
    # Pegar o nome do primeiro BIN e remover (Track X)
    first_bin = bins[0]
    cue_stem = re.sub(r'\s*\(Track\s*\d+\)\s*$', '', first_bin.stem, flags=re.I)
    cue_path = parent / f"{cue_stem}.cue"
    
    # Verificar se ja tem CHD
    serial = extract_serial(cue_stem)
    if serial and serial in chd_serials:
        continue
    if cue_stem.lower() in chd_stems:
        continue
    
    # Gerar CUE multi-track
    cue_lines = []
    for bin_path in bins:
        track_n = track_num(bin_path.stem)
        if track_n == 1:
            mode = "MODE2/2352"
            cue_lines.append(f'FILE "{bin_path.name}" BINARY')
            cue_lines.append(f'  TRACK 01 MODE2/2352')
            cue_lines.append(f'    INDEX 01 00:00:00')
        else:
            cue_lines.append(f'FILE "{bin_path.name}" BINARY')
            cue_lines.append(f'  TRACK {track_n:02d} AUDIO')
            cue_lines.append(f'    INDEX 00 00:00:00')
            cue_lines.append(f'    INDEX 01 00:02:00')
    
    cue_content = "\n".join(cue_lines) + "\n"
    
    existed = cue_path.exists()
    try:
        cue_path.write_text(cue_content, encoding="utf-8")
        if existed:
            cues_regenerated += 1
        else:
            cues_created += 1
    except Exception as e:
        if cues_created + cues_regenerated < 5:
            print(f"  ERRO: {cue_path.name}: {e}")

print(f"  CUEs multi-track regenerados: {cues_regenerated}")
print(f"  CUEs multi-track criados:     {cues_created}")

# ============================================================
# 6. GERAR CUEs SINGLE-TRACK PARA BINS AINDA SEM CUE
# ============================================================
print("\n=== 6. GERANDO CUES SINGLE-TRACK RESTANTES ===")
cues_single = 0
for base in [PSX, DUP]:
    if not base.exists(): continue
    for f in base.glob("*.bin"):
        # Ja tem CUE com mesmo nome?
        if f.with_suffix(".cue").exists():
            continue
        # Ja tem CHD?
        serial = extract_serial(f.stem)
        if serial and serial in chd_serials:
            continue
        if normalize_base(f.stem) in chd_stems:
            continue
        # E multi-track? (existem outros BINs com mesmo base)
        base_name = normalize_base(f.stem)
        parent = str(f.parent)
        if len(all_bins.get((parent, base_name), [])) > 1:
            continue  # multi-track ja tratado acima
        
        # Single-track sem CUE - gerar
        cue_path = f.with_suffix(".cue")
        cue_content = f'FILE "{f.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
        try:
            cue_path.write_text(cue_content, encoding="utf-8")
            cues_single += 1
        except:
            pass
print(f"  CUEs single-track gerados: {cues_single}")

# ============================================================
# RESUMO
# ============================================================
print(f"\n{'='*60}")
print(f"RESUMO FINAL")
print(f"  BINs com CHD deletados de dup/:     {deleted_chd}")
print(f"  BINs restaurados de dup/ -> psx/:   {restored_to_psx}")
print(f"  CUEs multi-track regenerados:       {cues_regenerated}")
print(f"  CUEs multi-track criados:           {cues_created}")
print(f"  CUEs single-track gerados:          {cues_single}")
print(f"  Total CUEs gerados/regenerados:     {cues_regenerated + cues_created + cues_single}")
print(f"{'='*60}")
