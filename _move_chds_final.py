"""Move CHDs prontos de F:\\chd_temp para D:\\roms\\library\\roms\\psx."""
import os, shutil, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SRC = Path(r'F:\chd_temp')
DST = Path(r'D:\roms\library\roms\psx')

if not SRC.exists():
    print(f'{SRC} nao existe')
    sys.exit(0)

chds = sorted(SRC.glob('*.chd'))
print(f'CHDs em F:\\chd_temp: {len(chds)}')

moved = 0
skipped = 0
errors = 0
total_saved = 0

for chd in chds:
    dst = DST / chd.name
    try:
        if dst.exists():
            # Ja existe no destino — verificar se e maior/igual
            src_sz = chd.stat().st_size
            dst_sz = dst.stat().st_size
            if dst_sz >= src_sz:
                # Destino ja tem o arquivo — apagar origem
                chd.unlink()
                skipped += 1
                total_saved += src_sz
                continue
        # Mover
        shutil.move(str(chd), str(dst))
        moved += 1
        sz_mb = chd.stat().st_size if chd.exists() else 0
        # Nao printar cada um para economizar contexto
    except Exception as e:
        errors += 1
        print(f'ERRO: {chd.name}: {e}')

print(f'\nMovidos: {moved}')
print(f'Skipped (ja existiam): {skipped}')
print(f'Erros: {errors}')
print(f'Espaco recuperado em F: {total_saved/1e9:.1f} GB')

# Listar restantes
remaining = list(SRC.glob('*.chd'))
print(f'Restantes em F:\\chd_temp: {len(remaining)}')

# Tambem mover arquivos auxiliares (cue, bin, etc) que foram fontes de conversao
# NAO mover — esses ja foram movidos para duplicados pelo pipeline
