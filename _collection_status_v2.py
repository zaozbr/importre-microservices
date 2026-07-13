"""
Verifica o status completo da colecao PSX:
- Total na colecao original
- Total baixado
- Total faltando
- Gera relatorio detalhado
"""
import json, os, sys, glob
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STATE_DIR = r'D:\roms\library\roms\_importre_state'
DOWNLOADS_DIR = os.path.join(STATE_DIR, 'downloads')
QUEUE_PATH = os.path.join(STATE_DIR, 'queue.json')

def main():
    # Queue status
    q = json.load(open(QUEUE_PATH, encoding='utf-8'))
    completed = q.get('completed', {})
    failed = q.get('failed', {})
    pending = q.get('queue', [])
    in_progress = q.get('in_progress', {})
    total = q.get('total', 0)

    print('=' * 60)
    print('  STATUS DA COLECAO PSX')
    print('=' * 60)
    print(f'  Total registrado: {total}')
    print(f'  Completados: {len(completed)}')
    print(f'  Falhados: {len(failed)}')
    print(f'  Pendentes: {len(pending)}')
    print(f'  Em progresso: {len(in_progress)}')

    # Arquivos em disco
    rom_files = []
    for ext in ['*.bin', '*.img', '*.iso', '*.zip', '*.7z']:
        rom_files.extend(glob.glob(os.path.join(DOWNLOADS_DIR, ext)))
    print(f'\n  Arquivos em disco: {len(rom_files)}')

    total_size = sum(os.path.getsize(f) for f in rom_files if os.path.exists(f))
    print(f'  Tamanho total: {total_size / 1024 / 1024 / 1024:.1f} GB')

    # Verificar colecao original
    col_paths = [
        r'D:\roms\library\roms\psx\PSX_Colecao_Faltantes.md',
        r'D:\roms\library\roms\psx\PSX_Colecao_Completa.md',
    ]
    for col_path in col_paths:
        if os.path.exists(col_path):
            with open(col_path, 'r', encoding='utf-8') as cf:
                lines = [l.strip() for l in cf if l.strip() and not l.startswith('#') and not l.startswith('--')]
            print(f'\n  Colecao: {os.path.basename(col_path)}')
            print(f'  Itens na lista: {len(lines)}')

            # Verificar quais faltam
            missing = []
            for line in lines:
                parts = line.split('|')
                serial = parts[0].strip() if parts else line.strip()
                if serial and serial not in completed:
                    missing.append(serial)
            print(f'  Faltando baixar: {len(missing)}')
            if missing:
                print(f'  Primeiros 20 faltando:')
                for m in missing[:20]:
                    print(f'    {m}')

    # Falhas detalhadas
    print(f'\n  FALHAS ({len(failed)}):')
    for serial, info in failed.items():
        reason = info.get('reason', '?') if isinstance(info, dict) else str(info)
        name = info.get('name', '') if isinstance(info, dict) else ''
        print(f'    {serial}: {reason} - {name}')

    # Verificar cross_index_results
    cross_path = os.path.join(STATE_DIR, 'cross_index_results.json')
    if os.path.exists(cross_path):
        cross = json.load(open(cross_path, encoding='utf-8'))
        print(f'\n  Cross-index results: {len(cross)} itens')
        # Verificar se algum dos falhados esta no cross-index
        for serial, _ in failed.items():
            if serial in cross:
                info = cross[serial]
                print(f'    {serial} no cross-index: {info}')

    print(f'\n{"=" * 60}')
    pct = len(completed) / max(total, 1) * 100
    print(f'  PROGRESSO: {pct:.1f}% ({len(completed)}/{total})')
    print(f'{"=" * 60}')


if __name__ == '__main__':
    main()
