"""Deleta arquivos parciais de download (incompletos) baseado em dl_progress.json."""
import json, os

PROGRESS = r'D:\roms\library\roms\_importre_state\dl_progress.json'
DOWNLOADS = r'D:\roms\library\roms\_importre_state\downloads'

# Carregar progresso
progress = {}
if os.path.exists(PROGRESS):
    with open(PROGRESS, 'r', encoding='utf-8') as f:
        progress = json.load(f)

# Deletar arquivos parciais
deleted = 0
if progress:
    for key, info in progress.items():
        if not isinstance(info, dict):
            continue
        serial = info.get('serial', key)
        total = info.get('total', 0)
        downloaded = info.get('downloaded', 0)
        if total > 0 and downloaded < total:
            # Download incompleto - procurar e deletar arquivo
            for fn in os.listdir(DOWNLOADS):
                if fn.startswith(serial + '_'):
                    filepath = os.path.join(DOWNLOADS, fn)
                    size = os.path.getsize(filepath)
                    if size < total:
                        print(f'Deletando parcial: {fn} ({size//1024}KB / {total//1024}KB)')
                        os.remove(filepath)
                        deleted += 1

# Limpar dl_progress.json
with open(PROGRESS, 'w', encoding='utf-8') as f:
    json.dump({}, f)

print(f'\nDeletados: {deleted} arquivos parciais')
print('dl_progress.json limpo')
