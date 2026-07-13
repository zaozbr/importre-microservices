"""Salva lista final de faltantes em arquivo."""
import json

d = json.load(open(r'D:\roms\library\roms\_importre_state\missing_analysis.json'))
missing = d['missing_commercial']

# Salvar em arquivo de texto
with open(r'D:\roms\library\roms\_importre_state\missing_final.txt', 'w', encoding='utf-8') as f:
    f.write(f'=== ROMs COMERCIAIS FALTANTES: {len(missing)} ===\n\n')
    for serial, name in sorted(missing.items()):
        f.write(f'{serial}\t{name}\n')

print(f'Lista salva: {len(missing)} ROMs faltantes')
print(f'Arquivo: D:\\roms\\library\\roms\\_importre_state\\missing_final.txt')
