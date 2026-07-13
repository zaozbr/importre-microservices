#!/usr/bin/env python3
"""Gera CUEs para os 9 BINs em subpastas e move tudo para a raiz de psx/."""
import sys, re, shutil
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from collections import defaultdict

PSX = Path(r"D:\roms\library\roms\psx")

def track_num(name):
    m = re.search(r'Track\s*0*(\d+)', name, re.I)
    return int(m.group(1)) if m else 1

def normalize_base(name):
    s = re.sub(r'\s*\(Track\s*\d+\)\s*$', '', name, flags=re.I)
    s = re.sub(r'\s*\(CD\s*\d+\)\s*', '', s, flags=re.I)
    return s.strip()

# Os 9 BINs encontrados
targets = [
    r"D:\roms\library\roms\psx\Dance Dance Revolution - Extra Mix (Japan)\Dance Dance Revolution - Extra Mix (Japan).bin",
    r"D:\roms\library\roms\psx\release\nortis.bin",
    r"D:\roms\library\roms\psx\_chd_failed\Battle-Master-SLPS-01064.bin",
    r"D:\roms\library\roms\psx\Melty Lancer│銀河少女警察_II\CD1\銀河少女警察_II (CD1) (Track 1).bin",
    r"D:\roms\library\roms\psx\Melty Lancer│銀河少女警察_II\CD1\銀河少女警察_II (CD1) (Track 2).bin",
    r"D:\roms\library\roms\psx\Melty Lancer│銀河少女警察_II\CD1\銀河少女警察_II (CD1) (Track 3).bin",
    r"D:\roms\library\roms\psx\Melty Lancer│銀河少女警察_II\CD2\銀河少女警察_II (CD2) (Track 1).bin",
    r"D:\roms\library\roms\psx\Melty Lancer│銀河少女警察_II\CD2\銀河少女警察_II (CD2) (Track 2).bin",
]

# Agrupar por diretorio
groups = defaultdict(list)
for t in targets:
    p = Path(t)
    if p.exists():
        groups[str(p.parent)].append(p)

print("=== GERANDO CUEs E MOVENDO PARA RAIZ DE psx/ ===")
moved = 0
cues = 0

for dir_str, bins in groups.items():
    parent = Path(dir_str)
    bins.sort(key=lambda f: track_num(f.stem))
    
    if len(bins) == 1:
        # Single track
        bin_path = bins[0]
        # Mover BIN para raiz de psx/
        dest_bin = PSX / bin_path.name
        if not dest_bin.exists():
            shutil.move(str(bin_path), str(dest_bin))
            moved += 1
        # Gerar CUE
        cue_path = dest_bin.with_suffix(".cue")
        cue_content = f'FILE "{dest_bin.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
        cue_path.write_text(cue_content, encoding="utf-8")
        cues += 1
        print(f"  [single] {dest_bin.name[:60]}")
    else:
        # Multi-track - agrupar por CD
        cd_groups = defaultdict(list)
        for b in bins:
            m = re.search(r'\(CD\s*(\d+)\)', b.stem, re.I)
            cd = m.group(1) if m else "1"
            cd_groups[cd].append(b)
        
        for cd, cd_bins in cd_groups.items():
            cd_bins.sort(key=lambda f: track_num(f.stem))
            # Mover todos os BINs para raiz
            for b in cd_bins:
                dest = PSX / b.name
                if not dest.exists():
                    shutil.move(str(b), str(dest))
                    moved += 1
            # Gerar CUE multi-track
            base_name = normalize_base(cd_bins[0].stem)
            cue_path = PSX / f"{base_name} (CD{cd}).cue"
            cue_lines = []
            for b in cd_bins:
                dest = PSX / b.name
                tn = track_num(b.stem)
                if tn == 1:
                    cue_lines.append(f'FILE "{dest.name}" BINARY')
                    cue_lines.append(f'  TRACK 01 MODE2/2352')
                    cue_lines.append(f'    INDEX 01 00:00:00')
                else:
                    cue_lines.append(f'FILE "{dest.name}" BINARY')
                    cue_lines.append(f'  TRACK {tn:02d} AUDIO')
                    cue_lines.append(f'    INDEX 00 00:00:00')
                    cue_lines.append(f'    INDEX 01 00:02:00')
            cue_path.write_text("\n".join(cue_lines) + "\n", encoding="utf-8")
            cues += 1
            print(f"  [multi {len(cd_bins)} tracks] {cue_path.name[:60]}")

# Limpar subpastas vazias
for dir_str in groups:
    d = Path(dir_str)
    try:
        if d.exists() and not any(d.iterdir()):
            d.rmdir()
            print(f"  Pasta vazia removida: {d.name}")
    except:
        pass
# Tambem limpar pais
try:
    melty = PSX / "Melty Lancer│銀河少女警察_II"
    if melty.exists():
        for sub in melty.iterdir():
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()
        if not any(melty.iterdir()):
            melty.rmdir()
            print(f"  Pasta vazia removida: Melty Lancer")
except:
    pass

print(f"\nBINs movidos: {moved}")
print(f"CUEs gerados: {cues}")
