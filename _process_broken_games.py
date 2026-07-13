"""Extrai todos os jogos com problema do log do DuckStation e prepara para redownload."""
import sys, os, re, json, shutil
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LOG_FILE = Path(r'D:\roms\library\roms\psx\lista de jogos duckstation.txt')
PSX_DIR = Path(r'D:\roms\library\roms\psx')
BROKEN_DIR = Path(r'D:\roms\chd-quebrados-psx')
QUEUE_FILE = Path(r'D:\roms\library\roms\psx\_redownload_queue.json')

SERIAL_RE = re.compile(r'\b(SLUS|SLPS|SLPM|SLES|SCES|SCUS|SCPS|SLED|SLKA|SIPS)(?:-|\s)?(\d{3,5})\b', re.IGNORECASE)

def extract_serial(text):
    m = SERIAL_RE.search(text)
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    return None

def main():
    with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    print(f"Log tem {len(lines)} linhas")
    
    # Categorias de erro:
    # 1. E(OpenCHD): Failed to open CHD '...' -> CHD invalido/corrompido
    # 2. E(GetDiscListEntry): Failed to open disc image '...' -> CUE/CCD sem BIN/IMG
    # 3. E(ReadExecutableFromImage): Failed to read executable 'PSX.EXE' from disc -> CHD sem executable
    # 4. W(IsValidPSExeHeader): Incorrect file size -> PS-EXE invalido
    
    broken_chds = set()  # CHDs corrompidos
    broken_cues = set()  # CUE/CCD sem BIN/IMG
    broken_exe = set()   # CHD sem PSX.EXE
    broken_header = set()  # PS-EXE header invalido
    
    # Mapear nome do arquivo -> nome do jogo (da linha de "Varredura" anterior)
    current_scan = None
    scan_map = {}  # filename -> scan name
    
    for i, line in enumerate(lines):
        # Track current scan
        m_scan = re.search(r"Status: Varredura '([^']+)'", line)
        if m_scan:
            current_scan = m_scan.group(1)
            continue
        
        # E(OpenCHD): Failed to open CHD 'path'
        m = re.search(r"E\(OpenCHD\): Failed to open CHD '([^']+)'", line)
        if m:
            chd_path = Path(m.group(1))
            broken_chds.add(chd_path.name)
            continue
        
        # E(GetDiscListEntry): Failed to open disc image 'name': ...
        m = re.search(r"E\(GetDiscListEntry\): Failed to open disc image '([^']+)'", line)
        if m:
            disc_name = m.group(1)
            # Ignorar chdman.exe
            if 'chdman' in disc_name.lower():
                continue
            broken_cues.add(disc_name)
            continue
        
        # E(ReadExecutableFromImage): Failed to read executable 'PSX.EXE' from disc
        if "E(ReadExecutableFromImage): Failed to read executable 'PSX.EXE' from disc" in line:
            if current_scan:
                broken_exe.add(current_scan)
            continue
        
        # W(IsValidPSExeHeader): Incorrect file size
        if "W(IsValidPSExeHeader): Incorrect file size" in line:
            if current_scan:
                broken_header.add(current_scan)
            continue
    
    # Compilar lista unificada de jogos com problema
    # Cada entrada: { serial, name, filename, type, action }
    all_broken = {}
    
    for name in broken_chds:
        serial = extract_serial(name)
        clean = name.replace('.chd', '').replace('-nao-conversivel', '')
        all_broken[name] = {
            'serial': serial,
            'name': clean,
            'filename': name,
            'error_type': 'chd_invalid',
            'description': 'CHD corrompido/invalido',
        }
    
    for name in broken_cues:
        serial = extract_serial(name)
        clean = name.replace('-nao-conversivel', '')
        # Determinar extensao
        ext = Path(name).suffix.lower()
        all_broken[name] = {
            'serial': serial,
            'name': clean,
            'filename': name,
            'error_type': 'missing_data',
            'description': f'Arquivo {ext} sem dados (BIN/IMG ausente)',
        }
    
    for name in broken_exe:
        serial = extract_serial(name)
        clean = name.replace('-nao-conversivel', '')
        all_broken[name] = {
            'serial': serial,
            'name': clean,
            'filename': name,
            'error_type': 'no_executable',
            'description': 'CHD sem PSX.EXE executavel',
        }
    
    for name in broken_header:
        serial = extract_serial(name)
        clean = name.replace('-nao-conversivel', '')
        all_broken[name] = {
            'serial': serial,
            'name': clean,
            'filename': name,
            'error_type': 'bad_header',
            'description': 'PS-EXE header invalido',
        }
    
    # Estatisticas
    print(f"\n{'='*70}")
    print(f"  JOGOS COM PROBLEMA NO DUCKSTATION")
    print(f"{'='*70}")
    print(f"  CHDs corrompidos:       {len(broken_chds)}")
    print(f"  CUE/CCD sem BIN/IMG:    {len(broken_cues)}")
    print(f"  CHD sem PSX.EXE:        {len(broken_exe)}")
    print(f"  PS-EXE header invalido: {len(broken_header)}")
    print(f"  TOTAL UNICO:            {len(all_broken)}")
    
    # Listar todos
    by_type = {}
    for item in all_broken.values():
        t = item['error_type']
        by_type.setdefault(t, []).append(item)
    
    for t, items in sorted(by_type.items()):
        print(f"\n--- {t} ({len(items)}) ---")
        for item in sorted(items, key=lambda x: x['serial'] or 'zzz'):
            sr = item['serial'] or '????'
            print(f"  {sr:12s} | {item['filename'][:60]}")
    
    # Salvar lista
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(all_broken.values()), f, ensure_ascii=False, indent=2)
    print(f"\nLista salva em: {QUEUE_FILE}")
    
    # Mover arquivos quebrados para D:\roms\chd-quebrados-psx
    BROKEN_DIR.mkdir(parents=True, exist_ok=True)
    
    moved = 0
    not_found = 0
    errors = 0
    
    print(f"\n{'='*70}")
    print(f"  MOVENDO ARQUIVOS QUEBRADOS PARA {BROKEN_DIR}")
    print(f"{'='*70}")
    
    for name, item in all_broken.items():
        # Procurar arquivo no PSX_DIR
        src = PSX_DIR / name
        if not src.exists():
            # Tentar sem -nao-conversivel
            clean_name = name.replace('-nao-conversivel', '')
            src = PSX_DIR / clean_name
        if not src.exists():
            # Procurar por pattern
            pattern = name.replace('-nao-conversivel', '*')
            matches = list(PSX_DIR.glob(pattern))
            if matches:
                src = matches[0]
            else:
                not_found += 1
                continue
        
        try:
            dst = BROKEN_DIR / src.name
            if dst.exists():
                dst = BROKEN_DIR / f"{src.stem}_{int(time.time())}{src.suffix}"
            shutil.move(str(src), str(dst))
            moved += 1
            print(f"  MOVIDO: {src.name}")
        except Exception as e:
            errors += 1
            print(f"  ERRO: {src.name}: {e}")
    
    print(f"\nMovidos: {moved}")
    print(f"Nao encontrados: {not_found}")
    print(f"Erros: {errors}")
    
    # Tambem mover arquivos relacionados (CUE + BIN do mesmo jogo)
    print(f"\n{'='*70}")
    print(f"  MOVENDO ARQUIVOS RELACIONADOS (CUE+BIN+CCD+IMG)")
    print(f"{'='*70}")
    
    for name, item in all_broken.items():
        base = Path(name).stem.replace('-nao-conversivel', '')
        for ext in ['.cue', '.bin', '.ccd', '.img', '.mds', '.mdf', '.ecm', '.sub']:
            src = PSX_DIR / f"{base}{ext}"
            if src.exists():
                try:
                    dst = BROKEN_DIR / src.name
                    if dst.exists():
                        continue  # Ja movido
                    shutil.move(str(src), str(dst))
                    moved += 1
                    print(f"  MOVIDO: {src.name}")
                except Exception as e:
                    errors += 1
                    print(f"  ERRO: {src.name}: {e}")
    
    print(f"\nTOTAL movidos: {moved}")
    print(f"Nao encontrados: {not_found}")
    print(f"Erros: {errors}")


if __name__ == '__main__':
    import time
    main()
