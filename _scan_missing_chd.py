"""
Scanner completo: encontra todos os jogos PSX sem CHD em D:\roms\library\roms\psx e subpastas.
Gera lista detalhada com serial, nome, arquivos fonte, tamanho e caminho.
"""
import os, sys, re, json, glob
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX_DIR = Path(r'D:\roms\library\roms\psx')
ROM_EXTS = {'.bin', '.img', '.iso', '.ecm', '.cue', '.mds', '.ccd'}
CHD_EXT = '.chd'

# Serial regex
SERIAL_RE = re.compile(r'\b(SLUS|SLPS|SLPM|SLES|SCES|SCUS|SCPS|SLED|SLKA|SLPS|SIPS)(?:-|\s)?(\d{3,5})\b', re.IGNORECASE)


def extract_serial(name):
    """Extrai serial do nome do arquivo."""
    m = SERIAL_RE.search(name)
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    return None


def find_chd_for_name(base_name, directory):
    """Verifica se existe um .chd correspondente ao nome base."""
    # Procura por {base_name}.chd no mesmo diretorio e no diretorio pai
    for d in [directory, directory.parent, PSX_DIR]:
        if d is None or not d.exists():
            continue
        chd = d / f"{base_name}.chd"
        if chd.exists():
            return chd
        # Procura por chd que contenha o base_name
        for f in d.glob(f"*{base_name}*.chd"):
            return f
    return None


def find_chd_for_serial(serial, directory):
    """Verifica se existe um .chd correspondente ao serial."""
    if not serial:
        return None
    for d in [directory, directory.parent, PSX_DIR]:
        if d is None or not d.exists():
            continue
        # Procura por *{serial}*.chd
        for f in d.glob(f"*{serial}*.chd"):
            return f
    return None


def scan_directory(directory):
    """Escaneia um diretorio procurando ROMs sem CHD correspondente."""
    missing = []
    
    for root, dirs, files in os.walk(directory):
        root_path = Path(root)
        
        # Pular pastas que nao sao de ROMs
        rel = root_path.relative_to(directory)
        parts = rel.parts
        if any(p.startswith('_') or p.startswith('.') for p in parts):
            continue
        if 'duplicados' in str(rel) or 'duplicado' in str(rel):
            # Estas pastas tem fontes - incluir
            pass
        
        # Agrupar arquivos por nome base (sem extensao)
        rom_files = []
        for f in files:
            ext = Path(f).suffix.lower()
            if ext in ROM_EXTS:
                rom_files.append(f)
        
        if not rom_files:
            continue
        
        # Agrupar por nome base
        groups = {}
        for f in rom_files:
            base = Path(f).stem
            # Normalizar: remover "(Track N)" do nome base
            base_clean = re.sub(r'\s*\(Track\s+\d+\)\s*', '', base)
            if base_clean not in groups:
                groups[base_clean] = []
            groups[base_clean].append((f, root_path))
        
        for base_name, file_list in groups.items():
            serial = extract_serial(base_name)
            
            # Verificar se ja existe CHD
            chd_path = find_chd_for_name(base_name, root_path)
            if not chd_path and serial:
                chd_path = find_chd_for_serial(serial, root_path)
            
            if chd_path and chd_path.exists():
                continue  # Ja tem CHD
            
            # Nao tem CHD - coletar informacoes
            total_size = 0
            file_infos = []
            for fname, fdir in file_list:
                fpath = fdir / fname
                try:
                    size = fpath.stat().st_size
                    total_size += size
                except:
                    size = 0
                file_infos.append({
                    'name': fname,
                    'path': str(fpath),
                    'size': size,
                })
            
            # Determinar tipo de fonte
            exts = set(Path(f[0]).suffix.lower() for f in file_list)
            if '.ecm' in exts:
                source_type = 'ecm'
            elif '.mds' in exts or '.ccd' in exts:
                source_type = 'mds_ccd'
            elif '.cue' in exts and '.bin' in exts:
                source_type = 'cue_bin'
            elif '.cue' in exts:
                source_type = 'cue_only'
            elif '.bin' in exts:
                source_type = 'bin'
            elif '.img' in exts:
                source_type = 'img'
            elif '.iso' in exts:
                source_type = 'iso'
            else:
                source_type = 'other'
            
            missing.append({
                'base_name': base_name,
                'serial': serial,
                'source_type': source_type,
                'total_size': total_size,
                'files': file_infos,
                'directory': str(root_path),
            })
    
    return missing


def main():
    print('=' * 70)
    print('  SCANNER COMPLETO: ROMs PSX sem CHD')
    print(f'  Diretorio: {PSX_DIR}')
    print('=' * 70)
    
    # Coletar todos os CHDs existentes
    all_chds = list(PSX_DIR.rglob('*.chd'))
    print(f'\nCHDs existentes: {len(all_chds)}')
    
    # Coletar todas as ROMs fonte
    all_roms = []
    for ext in ROM_EXTS:
        all_roms.extend(PSX_DIR.rglob(f'*{ext}'))
    print(f'ROMs fonte encontradas: {len(all_roms)}')
    
    # Escanear
    print('\nEscaneando diretorios...')
    missing = scan_directory(PSX_DIR)
    
    # Filtrar: remover itens que sao apenas .cue sem .bin (track-only)
    real_missing = []
    for item in missing:
        if item['source_type'] == 'cue_only':
            # Verificar se ha .bin correspondente em outro lugar
            base = item['base_name']
            has_bin = any(
                Path(f['name']).stem.startswith(base) and Path(f['name']).suffix == '.bin'
                for other in missing
                for f in other['files']
            )
            if has_bin:
                continue
        real_missing.append(item)
    
    # Ordenar por tamanho (menores primeiro)
    real_missing.sort(key=lambda x: x['total_size'])
    
    # Estatisticas por tipo
    by_type = {}
    for item in real_missing:
        t = item['source_type']
        by_type[t] = by_type.get(t, 0) + 1
    
    print(f'\n{"=" * 70}')
    print(f'  RESULTADO: {len(real_missing)} jogos sem CHD')
    print(f'{"=" * 70}')
    print(f'\nPor tipo de fonte:')
    for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f'  {t:15s}: {count}')
    
    total_size = sum(i['total_size'] for i in real_missing)
    print(f'\nTamanho total das fontes: {total_size / 1024 / 1024 / 1024:.1f} GB')
    
    # Listar todos
    print(f'\n{"=" * 70}')
    print(f'  LISTA DETALHADA (ordenada por tamanho)')
    print(f'{"=" * 70}')
    for i, item in enumerate(real_missing):
        size_mb = item['total_size'] / 1024 / 1024
        serial = item['serial'] or '????'
        print(f'\n[{i+1:4d}] {serial:12s} | {item["source_type"]:10s} | {size_mb:8.1f} MB')
        print(f'       Nome: {item["base_name"]}')
        print(f'       Dir:  {item["directory"]}')
        for f in item['files'][:3]:
            print(f'       Arq:  {f["name"]} ({f["size"]/1024/1024:.1f} MB)')
        if len(item['files']) > 3:
            print(f'       ... e mais {len(item["files"])-3} arquivos')
    
    # Salvar JSON
    output_path = PSX_DIR / '_missing_chd_list.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(real_missing, f, ensure_ascii=False, indent=2)
    print(f'\nLista salva em: {output_path}')
    
    # Salvar lista simples para processamento
    simple_path = PSX_DIR / '_missing_chd_simple.txt'
    with open(simple_path, 'w', encoding='utf-8') as f:
        for item in real_missing:
            serial = item['serial'] or '????'
            f.write(f"{serial}\t{item['base_name']}\t{item['source_type']}\t{item['total_size']}\t{item['directory']}\n")
    print(f'Lista simples salva em: {simple_path}')


if __name__ == '__main__':
    main()
