"""Verifica toda a colecao PSX em disco e compara com a lista de faltantes."""
import os, re, json

PSX_DIR = r'D:\roms\library\roms\psx'
STATE_DIR = r'D:\roms\library\roms\_importre_state'
MD_PATH = r'D:\roms\library\roms\PSX_Colecao_Faltantes.md'

# 1. Listar todos os arquivos ROM em disco
exts = {'.chd', '.bin', '.cue', '.zip', '.7z', '.iso', '.img', '.ecm', '.pbp'}
files = [f for f in os.listdir(PSX_DIR) if os.path.splitext(f)[1].lower() in exts]
print(f'Arquivos ROM em disco: {len(files)}')

# 2. Extrair seriais dos nomes dos arquivos
serials_on_disk = set()
for f in files:
    # Padroes: SLUS-01234, SLES-00567, SLPS-00890, SLPM-86888, SCUS-94200, SLED-02309, ESPM-70002, HBREW-001
    matches = re.findall(r'(S[LC][EUP]S?-\d{4,5}|SCUS-\d{5}|ESPM-\d{5}|HBREW-\d{3})', f.upper())
    for m in matches:
        serials_on_disk.add(m)

print(f'Seriais unicos em disco: {len(serials_on_disk)}')

# 3. Carregar lista de faltantes do MD
all_needed = {}
with open(MD_PATH, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('|') and not line.startswith('|#') and not line.startswith('|-') and not line.startswith('| #'):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4:
                serial = parts[2]  # | # | Serial | Nome |
                name = parts[3]
                # Validar serial
                if re.match(r'^(S[LC][EUP]S?-\d{4,5}|SCUS-\d{5}|ESPM-\d{5}|HBREW-\d{3})$', serial):
                    all_needed[serial] = name

print(f'Total na lista de faltantes (MD): {len(all_needed)}')

# 4. Carregar queue.json
QUEUE_PATH = os.path.join(STATE_DIR, 'queue.json')
with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
    q = json.load(f)

completed = q.get('completed', {})
if not isinstance(completed, dict):
    completed = {}
failed = q.get('failed', {})
if not isinstance(failed, dict):
    failed = {}
in_progress = q.get('in_progress', {})
if not isinstance(in_progress, dict):
    in_progress = {}
queue = q.get('queue', [])

print(f'Queue: pending={len(queue)} completed={len(completed)} failed={len(failed)} in_progress={len(in_progress)}')

# 5. Downloads temporarios
downloads_dir = os.path.join(STATE_DIR, 'downloads')
downloaded_temp = {}
if os.path.exists(downloads_dir):
    for f in os.listdir(downloads_dir):
        if f.endswith('.download'):
            serial = f.replace('.download', '')
            size = os.path.getsize(os.path.join(downloads_dir, f))
            if size > 100 * 1024:
                downloaded_temp[serial] = size

print(f'Downloads temporarios (>100KB): {len(downloaded_temp)}')

# 6. Determinar o que realmente falta
have = set()
have |= serials_on_disk
have |= set(completed.keys())
have |= set(downloaded_temp.keys())

# Faltantes reais
really_missing = {}
for serial, name in all_needed.items():
    if serial not in have:
        really_missing[serial] = name

# Estatisticas por tipo
have_commercial = len([s for s in have if s.startswith(('SL', 'SC'))])
have_homebrew = len([s for s in have if s.startswith('HBREW')])
have_espm = len([s for s in have if s.startswith('ESPM')])

missing_commercial = {s: n for s, n in really_missing.items() if s.startswith(('SL', 'SC'))}
missing_homebrew = {s: n for s, n in really_missing.items() if s.startswith('HBREW')}
missing_espm = {s: n for s, n in really_missing.items() if s.startswith('ESPM')}

print(f'\n=== RESUMO ===')
print(f'Ja tem: {len(have & set(all_needed.keys()))} de {len(all_needed)}')
print(f'Realmente faltando: {len(really_missing)}')
print(f'  - Comerciais (SL/SC): {len(missing_commercial)}')
print(f'  - Homebrew (HBREW): {len(missing_homebrew)}')
print(f'  - ESPM: {len(missing_espm)}')

# 7. Listar faltantes COMERCIAIS (prioridade)
print(f'\n=== ROMs COMERCIAIS FALTANTES ({len(missing_commercial)}) ===')
for serial, name in sorted(missing_commercial.items()):
    in_q = serial in [item.get('serial') for item in queue if isinstance(item, dict)]
    in_ip = serial in in_progress
    in_fl = serial in failed
    status = ''
    if in_ip:
        status = ' [IN_PROGRESS]'
    elif in_fl:
        reason = failed[serial].get('reason', '?') if isinstance(failed.get(serial), dict) else '?'
        status = f' [FAILED: {reason[:30]}]'
    elif in_q:
        status = ' [PENDING]'
    print(f'  {serial}: {name[:50]}{status}')

# 8. Listar faltantes HOMEBREW (resumo)
print(f'\n=== HOMEBREW FALTANTES: {len(missing_homebrew)} ===')
if missing_homebrew:
    for serial, name in sorted(missing_homebrew.items())[:10]:
        print(f'  {serial}: {name[:50]}')
    if len(missing_homebrew) > 10:
        print(f'  ... e mais {len(missing_homebrew) - 10}')

# Salvar
result = {
    'total_on_disk': len(serials_on_disk),
    'total_needed': len(all_needed),
    'really_missing': really_missing,
    'missing_commercial': missing_commercial,
    'missing_homebrew': missing_homebrew,
    'missing_espm': missing_espm,
    'downloaded_temp': downloaded_temp,
}
out_path = os.path.join(STATE_DIR, 'missing_analysis.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f'\nSalvo em: {out_path}')
