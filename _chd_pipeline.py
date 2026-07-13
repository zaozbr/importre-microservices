"""
Pipeline final de conversao CHD — PSX
=====================================
1. Escaneia D:\roms\library\roms\psx por ROMs sem CHD
2. Classifica: converter (fonte valida) vs buscar_chd (fonte ausente/problematica)
3. Converte com chdman em F:\chd_temp (SSD rapido)
4. Verifica com chdman verify
5. Move fontes para D:\roms\duplicados apos conversao bem-sucedida
6. Move CHDs de F:\chd_temp para D:\roms\library\roms\psx

Uso:
    python _chd_pipeline.py                    # converte tudo
    python _chd_pipeline.py --workers 4        # 4 conversoes paralelas
    python _chd_pipeline.py --dry-run          # so lista, nao converte
    python _chd_pipeline.py --verify-only      # so verifica CHDs em F:\chd_temp
    python _chd_pipeline.py --move-final       # move CHDs de F:\chd_temp para colecao
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent))

# Config
PSX_DIR = Path(r"D:\roms\library\roms\psx")
CHD_TEMP = Path(r"F:\chd_temp")
DUPLICADOS = Path(r"D:\roms\duplicados")
CHDMAN = str(PSX_DIR / "chdman.exe")
PROGRESS_FILE = PSX_DIR / "_chd_pipeline_progress.json"
LOG_FILE = PSX_DIR / "_chd_pipeline.log"

ROM_EXTS = {'.bin', '.img', '.iso', '.ecm', '.cue', '.mds', '.ccd', '.mdf'}
SERIAL_RE = re.compile(r'\b(SLUS|SLPS|SLPM|SLES|SCES|SCUS|SCPS|SLED|SLKA|SIPS)(?:-|\s)?(\d{3,5})\b', re.IGNORECASE)

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_lock = threading.Lock()
_log_lock = threading.Lock()

_state = {
    "total": 0,
    "converted": 0,
    "failed": 0,
    "skipped": 0,
    "verified": 0,
    "in_progress": {},
    "errors": [],
    "start_time": time.time(),
}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    with _log_lock:
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except:
            pass


def save_state():
    with _lock:
        try:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(_state, f, ensure_ascii=False, indent=2)
        except:
            pass


def extract_serial(name):
    m = SERIAL_RE.search(name)
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    return None


def sanitize_filename(name):
    for c in '<>:"/\\|?*':
        name = name.replace(c, '_')
    return name.strip()


def build_chd_name(serial, name):
    if serial and serial != "????":
        return f"{serial}.chd"
    return sanitize_filename(name) + ".chd"


def chd_exists_anywhere(chd_name):
    """Verifica se CHD ja existe na colecao ou no temp."""
    for d in [PSX_DIR, CHD_TEMP]:
        p = d / chd_name
        if p.exists() and p.stat().st_size > 1024:
            return True
    return False


# ============================================================
# SCAN: encontrar ROMs sem CHD
# ============================================================
def scan_missing():
    """Escaneia PSX_DIR por ROMs sem CHD correspondente."""
    missing = []
    
    for root, dirs, files in os.walk(PSX_DIR):
        root_path = Path(root)
        rel = root_path.relative_to(PSX_DIR)
        # Pular pastas internas
        if any(p.startswith('_') or p.startswith('.') for p in rel.parts):
            continue
        
        # Agrupar arquivos ROM por nome base (sem extensao e sem "(Track N)")
        rom_files = [f for f in files if Path(f).suffix.lower() in ROM_EXTS]
        if not rom_files:
            continue
        
        groups = {}
        for f in rom_files:
            base = Path(f).stem
            base_clean = re.sub(r'\s*\(Track\s+\d+\)\s*', '', base, flags=re.IGNORECASE)
            groups.setdefault(base_clean, []).append((f, root_path))
        
        for base_name, file_list in groups.items():
            serial = extract_serial(base_name)
            chd_name = build_chd_name(serial, base_name)
            
            if chd_exists_anywhere(chd_name):
                continue
            
            # Calcular tamanho total dos arquivos de dados (bin, img, iso, ecm, mdf)
            # Nao contar cue, ccd, mds (metadados)
            data_size = 0
            meta_size = 0
            file_infos = []
            for fname, fdir in file_list:
                fpath = fdir / fname
                ext = Path(fname).suffix.lower()
                try:
                    size = fpath.stat().st_size
                except:
                    size = 0
                if ext in {'.bin', '.img', '.iso', '.ecm', '.mdf'}:
                    data_size += size
                else:
                    meta_size += size
                file_infos.append({
                    'name': fname,
                    'path': str(fpath),
                    'size': size,
                    'ext': ext,
                })
            
            # Determinar tipo de fonte
            exts = set(Path(f[0]).suffix.lower() for f in file_list)
            has_cue = '.cue' in exts
            has_bin = '.bin' in exts
            has_img = '.img' in exts
            has_ccd = '.ccd' in exts
            has_mds = '.mds' in exts
            has_mdf = '.mdf' in exts
            has_iso = '.iso' in exts
            has_ecm = '.ecm' in exts
            
            if has_ecm:
                source_type = 'ecm'
            elif has_ccd and has_img:
                source_type = 'ccd_img'
            elif has_mds and has_mdf:
                source_type = 'mds_mdf'
            elif has_cue and has_bin:
                source_type = 'cue_bin'
            elif has_cue:
                source_type = 'cue_only'
            elif has_bin:
                source_type = 'bin'
            elif has_img:
                source_type = 'img'
            elif has_iso:
                source_type = 'iso'
            elif has_mdf:
                source_type = 'mdf'
            elif has_ccd:
                source_type = 'ccd_only'
            elif has_mds:
                source_type = 'mds_only'
            else:
                source_type = 'other'
            
            missing.append({
                'base_name': base_name,
                'serial': serial,
                'source_type': source_type,
                'data_size': data_size,
                'meta_size': meta_size,
                'total_size': data_size + meta_size,
                'files': file_infos,
                'directory': str(root_path),
                'chd_name': chd_name,
            })
    
    return missing


def classify(missing):
    """Classifica itens em converter, buscar_chd, ignorar."""
    converter = []
    buscar_chd = []
    ignorar = []
    seen = set()
    
    for item in missing:
        base = item['base_name']
        stype = item['source_type']
        data_size = item['data_size']
        
        base_clean = base.replace('-nao-conversivel', '')
        key = base_clean.lower()
        
        # Dedup: se ja vimos, decidir qual manter
        if key in seen:
            if '-nao-conversivel' in base:
                ignorar.append({**item, 'reason': 'duplicado_nao_conversivel'})
                continue
            # Substituir versao anterior se esta e melhor
            for lst, name in [(converter, 'converter'), (buscar_chd, 'buscar_chd')]:
                for i, it in enumerate(lst):
                    if it['base_name'].replace('-nao-conversivel', '').lower() == key:
                        if '-nao-conversivel' in it['base_name']:
                            ignorar.append({**it, 'reason': 'substituido'})
                            lst.pop(i)
                        else:
                            ignorar.append({**item, 'reason': 'ja_existe'})
                        break
            if key in seen and any(it['base_name'].replace('-nao-conversivel', '').lower() == key for it in ignorar if it.get('reason') == 'ja_existe'):
                continue
        
        seen.add(key)
        
        # Classificar
        has_data = data_size >= 1024  # pelo menos 1KB de dados
        
        if '-nao-conversivel' in base:
            buscar_chd.append({**item, 'action': 'buscar_chd'})
        elif stype in ('cue_only', 'ccd_only', 'mds_only'):
            buscar_chd.append({**item, 'action': 'buscar_chd'})
        elif not has_data:
            buscar_chd.append({**item, 'action': 'buscar_chd'})
        elif stype in ('cue_bin', 'bin', 'ccd_img', 'mds_mdf', 'img', 'iso', 'ecm', 'mdf'):
            converter.append({**item, 'action': 'converter'})
        else:
            converter.append({**item, 'action': 'converter'})
    
    converter.sort(key=lambda x: x['total_size'])
    buscar_chd.sort(key=lambda x: x['total_size'])
    return converter, buscar_chd, ignorar


# ============================================================
# CONVERSAO
# ============================================================
def generate_cue_for_bin(bin_path, cue_path):
    """Gera CUE basico para BIN single-track (MODE2/2352 — padrao PSX)."""
    try:
        size = bin_path.stat().st_size
        sectors = size // 2352
        if size % 2352 != 0:
            sectors = (size + 2351) // 2352
        with open(cue_path, 'w', encoding='utf-8') as f:
            f.write(f'FILE "{bin_path.name}" BINARY\n')
            f.write(f'  TRACK 01 MODE2/2352\n')
            f.write(f'    INDEX 01 00:00:00\n')
        return True
    except Exception as e:
        log(f"  generate_cue erro: {e}")
        return False


def ccd_to_cue(ccd_path, cue_path):
    """Converte CCD para CUE usando _ccd2cue helper."""
    try:
        from _ccd2cue import ccd_to_cue as _ccd2cue
        return _ccd2cue(str(ccd_path), str(cue_path))
    except Exception as e:
        log(f"  ccd_to_cue erro: {e}")
        return False


def find_cue_for_bin(bin_path):
    """Procura CUE correspondente ao BIN."""
    cue = bin_path.with_suffix('.cue')
    if cue.exists():
        return cue
    # Procura por CUE com nome similar
    for c in bin_path.parent.glob('*.cue'):
        if bin_path.stem.lower() in c.stem.lower():
            return c
    return None


def prepare_cue_for_chdman(cue_path, worker_id):
    """Prepara CUE para chdman: garante que BINs referenciados existam.
    Cria CUE temporario NO MESMO DIRETORIO do CUE original, com paths relativos.
    """
    try:
        with open(cue_path, 'rb') as f:
            raw = f.read(200)
        # Detectar encoding
        if (len(raw) >= 2 and (raw[0] == 0xFF and raw[1] == 0xFE or raw[0] == 0xFE and raw[1] == 0xFF)):
            encoding = 'utf-16'
        else:
            encoding = 'utf-8'
        with open(cue_path, 'r', encoding=encoding, errors='replace') as f:
            content = f.read()
        
        cue_dir = cue_path.parent
        lines = content.split('\n')
        new_lines = []
        needs_fix = False
        referenced_files = set()
        
        for line in lines:
            m = re.match(r'\s*FILE\s+"([^"]+)"\s+BINARY', line, re.IGNORECASE)
            if m:
                ref = m.group(1)
                ref_path = (cue_dir / ref)
                if ref_path.exists():
                    # Manter path relativo original (ja funciona)
                    referenced_files.add(ref_path.resolve())
                    new_lines.append(line)
                else:
                    # BIN referenciado nao existe — procurar substituto
                    base = Path(ref).stem.lower()
                    found = None
                    all_bins = sorted(cue_dir.glob('*.bin'), key=lambda x: x.stat().st_size, reverse=True)
                    # 1) Match fuzzy por palavras-chave
                    base_words = [w for w in re.split(r'[\s\-\(\)\[\]\.]+', base) if len(w) > 2]
                    for bf in all_bins:
                        bf_words = [w for w in re.split(r'[\s\-\(\)\[\]\.]+', bf.stem.lower()) if len(w) > 2]
                        common = set(base_words) & set(bf_words)
                        if len(common) >= min(2, len(base_words)):
                            found = bf
                            break
                    # 2) Match por Track number
                    if not found:
                        track_m = re.search(r'\(Track\s+(\d+)\)', ref, re.IGNORECASE)
                        if track_m:
                            track_num = track_m.group(1)
                            for bf in all_bins:
                                if f'(Track {track_num})' in bf.name or f'(Track {int(track_num):02})' in bf.name:
                                    found = bf
                                    break
                    # 3) Se so tem um BIN, usar ele
                    if not found and len(all_bins) == 1:
                        found = all_bins[0]
                    if found:
                        new_lines.append(f'FILE "{found.name}" BINARY')
                        referenced_files.add(found.resolve())
                        needs_fix = True
                    else:
                        new_lines.append(line)
            else:
                new_lines.append(line)
        
        if needs_fix:
            temp_cue = cue_dir / f"_temp_cue_w{worker_id}.cue"
            with open(temp_cue, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))
            return temp_cue, list(referenced_files)
        return cue_path, list(referenced_files)
    except Exception as e:
        log(f"  prepare_cue erro: {e}")
        return cue_path, []


def run_chdman(args, timeout=600):
    """Executa chdman com timeout."""
    cmd = [CHDMAN] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)


def verify_chd(chd_path):
    """Verifica CHD com chdman verify."""
    rc, out, err = run_chdman(["verify", "-i", str(chd_path)], timeout=120)
    return rc == 0, err or out


def move_source_to_duplicados(item):
    """Move arquivos fonte para D:\roms\duplicados apos conversao bem-sucedida."""
    DUPLICADOS.mkdir(parents=True, exist_ok=True)
    moved = []
    for f in item['files']:
        src = Path(f['path'])
        if src.exists():
            dst = DUPLICADOS / src.name
            # Evitar sobrescrever
            if dst.exists():
                dst = DUPLICADOS / f"{src.stem}_{int(time.time())}{src.suffix}"
            try:
                shutil.move(str(src), str(dst))
                moved.append(str(dst))
            except Exception as e:
                log(f"  erro ao mover {src.name}: {e}")
    return moved


def convert_one(item, worker_id):
    """Converte um item para CHD."""
    serial = item.get('serial') or ''
    name = item['base_name']
    chd_name = item['chd_name']
    chd_path = CHD_TEMP / chd_name
    stype = item['source_type']
    
    CHD_TEMP.mkdir(parents=True, exist_ok=True)
    
    # Skip se CHD ja existe
    if chd_path.exists() and chd_path.stat().st_size > 1024:
        # Verificar
        ok, msg = verify_chd(chd_path)
        if ok:
            log(f"[W{worker_id}] SKIP {chd_name} (ja existe e valido)")
            with _lock:
                _state["skipped"] += 1
            return "skipped"
        else:
            log(f"[W{worker_id}] CHD invalido existente, removendo: {chd_name}")
            chd_path.unlink()
    
    # Encontrar arquivo principal
    files = item['files']
    cue_file = None
    bin_file = None
    img_file = None
    ccd_file = None
    iso_file = None
    ecm_file = None
    mdf_file = None
    
    for f in files:
        ext = f['ext']
        fpath = Path(f['path'])
        if ext == '.cue':
            cue_file = fpath
        elif ext == '.bin':
            if bin_file is None or f['size'] > bin_file.stat().st_size:
                bin_file = fpath
        elif ext == '.img':
            img_file = fpath
        elif ext == '.ccd':
            ccd_file = fpath
        elif ext == '.iso':
            iso_file = fpath
        elif ext == '.ecm':
            ecm_file = fpath
        elif ext == '.mdf':
            mdf_file = fpath
    
    # Determinar input para chdman
    input_file = None
    temp_cue = None
    temp_files = []
    
    with _lock:
        _state["in_progress"][serial or name] = {
            "name": name,
            "chd": chd_name,
            "start_time": time.time(),
            "worker": worker_id,
            "type": stype,
        }
    save_state()
    
    try:
        if stype == 'cue_bin' and cue_file:
            input_file = cue_file
        elif stype == 'bin' and bin_file:
            # Gerar CUE automatico NO MESMO DIRETORIO do BIN
            temp_cue = bin_file.parent / f"_temp_{bin_file.stem}_w{worker_id}.cue"
            if generate_cue_for_bin(bin_file, temp_cue):
                input_file = temp_cue
            else:
                log(f"[W{worker_id}] FAIL {serial}: nao conseguiu gerar CUE para {bin_file.name}")
                with _lock:
                    _state["failed"] += 1
                    _state["errors"].append(f"{serial}: falha ao gerar CUE")
                return "failed"
        elif stype == 'ccd_img' and ccd_file and img_file:
            # Converter CCD para CUE NO MESMO DIRETORIO do IMG
            temp_cue = img_file.parent / f"_temp_{img_file.stem}_w{worker_id}.cue"
            if ccd_to_cue(ccd_file, temp_cue):
                input_file = temp_cue
            else:
                # Fallback: gerar CUE para IMG
                if generate_cue_for_bin(img_file, temp_cue):
                    input_file = temp_cue
                else:
                    log(f"[W{worker_id}] FAIL {serial}: CCD->CUE falhou")
                    with _lock:
                        _state["failed"] += 1
                        _state["errors"].append(f"{serial}: CCD->CUE falhou")
                    return "failed"
        elif stype == 'mds_mdf' and mdf_file:
            # MDF = binario, gerar CUE NO MESMO DIRETORIO
            temp_cue = mdf_file.parent / f"_temp_{mdf_file.stem}_w{worker_id}.cue"
            if generate_cue_for_bin(mdf_file, temp_cue):
                input_file = temp_cue
            else:
                log(f"[W{worker_id}] FAIL {serial}: MDF CUE falhou")
                with _lock:
                    _state["failed"] += 1
                    _state["errors"].append(f"{serial}: MDF CUE falhou")
                return "failed"
        elif stype == 'img' and img_file:
            temp_cue = img_file.parent / f"_temp_{img_file.stem}_w{worker_id}.cue"
            if generate_cue_for_bin(img_file, temp_cue):
                input_file = temp_cue
            else:
                log(f"[W{worker_id}] FAIL {serial}: IMG CUE falhou")
                with _lock:
                    _state["failed"] += 1
                    _state["errors"].append(f"{serial}: IMG CUE falhou")
                return "failed"
        elif stype == 'iso' and iso_file:
            input_file = iso_file
        elif stype == 'ecm' and ecm_file:
            # Decodificar ECM para BIN NO MESMO DIRETORIO
            temp_bin = ecm_file.parent / f"_temp_{ecm_file.stem}_w{worker_id}.bin"
            log(f"[W{worker_id}] ECM decode: {ecm_file.name}")
            ok = decode_ecm(ecm_file, temp_bin)
            if ok and temp_bin.exists():
                temp_cue = ecm_file.parent / f"_temp_{ecm_file.stem}_w{worker_id}.cue"
                generate_cue_for_bin(temp_bin, temp_cue)
                input_file = temp_cue
                temp_files.append(temp_bin)
            else:
                log(f"[W{worker_id}] FAIL {serial}: ECM decode falhou")
                with _lock:
                    _state["failed"] += 1
                    _state["errors"].append(f"{serial}: ECM decode falhou")
                return "failed"
        else:
            log(f"[W{worker_id}] FAIL {serial}: tipo {stype} sem arquivo principal")
            with _lock:
                _state["failed"] += 1
                _state["errors"].append(f"{serial}: {stype} sem arquivo")
            return "failed"
        
        # Preparar CUE (corrigir paths relativos se necessario)
        if input_file and str(input_file).lower().endswith('.cue'):
            prepared, refs = prepare_cue_for_chdman(input_file, worker_id)
            if prepared != input_file:
                if temp_cue:
                    try: temp_cue.unlink()
                    except: pass
                temp_cue = prepared
                input_file = prepared
        
        if not input_file or not input_file.exists():
            log(f"[W{worker_id}] FAIL {serial}: input nao encontrado")
            with _lock:
                _state["failed"] += 1
                _state["errors"].append(f"{serial}: input nao encontrado")
            return "failed"
        
        # Converter com chdman
        log(f"[W{worker_id}] CONVERT {serial} ({stype}) -> {chd_name}")
        rc, out, err = run_chdman([
            "createcd", "-i", str(input_file), "-o", str(chd_path), "-f"
        ], timeout=900)
        
        if rc != 0 or not chd_path.exists() or chd_path.stat().st_size < 1024:
            err_msg = (err or out or "erro desconhecido")[:200]
            log(f"[W{worker_id}] FAIL {serial}: chdman rc={rc}: {err_msg}")
            if chd_path.exists():
                try: chd_path.unlink()
                except: pass
            with _lock:
                _state["failed"] += 1
                _state["errors"].append(f"{serial}: chdman: {err_msg}")
            return "failed"
        
        # Verificar CHD
        ok, vmsg = verify_chd(chd_path)
        if not ok:
            log(f"[W{worker_id}] VERIFY FAIL {serial}: {vmsg[:200]}")
            try: chd_path.unlink()
            except: pass
            with _lock:
                _state["failed"] += 1
                _state["errors"].append(f"{serial}: verify: {vmsg[:200]}")
            return "failed"
        
        size_mb = chd_path.stat().st_size / 1024 / 1024
        log(f"[W{worker_id}] OK {serial}: {chd_name} ({size_mb:.1f} MB)")
        
        # Mover fontes para duplicados
        moved = move_source_to_duplicados(item)
        if moved:
            log(f"[W{worker_id}] FONTES movidas para duplicados: {len(moved)} arquivos")
        
        with _lock:
            _state["converted"] += 1
            _state["verified"] += 1
        return "converted"
    
    except Exception as e:
        log(f"[W{worker_id}] EXC {serial}: {e}")
        with _lock:
            _state["failed"] += 1
            _state["errors"].append(f"{serial}: {e}")
        return "failed"
    finally:
        # Limpar temp files
        if temp_cue:
            try: temp_cue.unlink()
            except: pass
        for tf in temp_files:
            try: tf.unlink()
            except: pass
        with _lock:
            _state["in_progress"].pop(serial or name, None)
        save_state()


def decode_ecm(ecm_path, bin_path):
    """Decodifica ECM para BIN (implementacao nativa Python)."""
    try:
        with open(ecm_path, 'rb') as f:
            data = f.read()
        
        # ECM header
        if not data.startswith(b'ECM'):
            return False, "header invalido"
        
        pos = 4  # pular "ECM\x00"
        out = bytearray()
        
        while pos < len(data):
            if pos >= len(data):
                break
            b = data[pos]
            pos += 1
            
            if b == 0xFF:
                # EOF
                break
            
            # Tipo de setor
            sector_type = b & 0x7F
            sector_size_map = {
                0: 2048,   # MODE1
                1: 2336,   # MODE2 form1/form2
                2: 2352,   # MODE2 raw
                3: 2336,   # MODE1 raw
            }
            sector_size = sector_size_map.get(sector_type, 2352)
            
            # Numero de setores (3 bytes big-endian)
            if pos + 3 > len(data):
                break
            num_sectors = (data[pos] << 16) | (data[pos+1] << 8) | data[pos+2]
            pos += 3
            
            for _ in range(num_sectors):
                if sector_type == 0:
                    # MODE1: dados 2048 + ECC 304 (interleaved)
                    if pos + 2048 > len(data):
                        break
                    out.extend(data[pos:pos+2048])
                    pos += 2048
                    # Pular ECC
                    ecc_size = sector_size - 2048
                    if ecc_size > 0:
                        pos += ecc_size
                else:
                    if pos + sector_size > len(data):
                        break
                    out.extend(data[pos:pos+sector_size])
                    pos += sector_size
        
        with open(bin_path, 'wb') as f:
            f.write(out)
        return True, f"{len(out)} bytes"
    except Exception as e:
        return False, str(e)


# ============================================================
# MOVE FINAL: F:\chd_temp -> D:\roms\library\roms\psx
# ============================================================
def move_final():
    """Move CHDs de F:\chd_temp para D:\roms\library\roms\psx."""
    chds = list(CHD_TEMP.glob('*.chd'))
    log(f"MOVENDO {len(chds)} CHDs de {CHD_TEMP} para {PSX_DIR}")
    moved = 0
    failed = 0
    for chd in chds:
        if chd.stat().st_size < 1024:
            log(f"  SKIP {chd.name} (arquivo muito pequeno)")
            continue
        dst = PSX_DIR / chd.name
        if dst.exists():
            log(f"  SKIP {chd.name} (ja existe no destino)")
            continue
        try:
            shutil.move(str(chd), str(dst))
            moved += 1
            if moved % 50 == 0:
                log(f"  ... {moved}/{len(chds)} movidos")
        except Exception as e:
            log(f"  FAIL {chd.name}: {e}")
            failed += 1
    log(f"MOVIMENTACAO CONCLUIDA: {moved} movidos, {failed} falharam")
    return moved, failed


# ============================================================
# VERIFY ONLY
# ============================================================
def verify_all():
    """Verifica todos os CHDs em F:\chd_temp."""
    chds = list(CHD_TEMP.glob('*.chd'))
    log(f"VERIFICANDO {len(chds)} CHDs em {CHD_TEMP}")
    ok = 0
    bad = 0
    for chd in chds:
        if chd.stat().st_size < 1024:
            log(f"  BAD {chd.name} (arquivo muito pequeno)")
            bad += 1
            continue
        valid, msg = verify_chd(chd)
        if valid:
            ok += 1
        else:
            log(f"  BAD {chd.name}: {msg[:100]}")
            bad += 1
    log(f"VERIFICACAO CONCLUIDA: {ok} OK, {bad} RUIM")
    return ok, bad


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--move-final', action='store_true')
    parser.add_argument('--list-only', action='store_true')
    args = parser.parse_args()
    
    if args.verify_only:
        verify_all()
        return
    
    if args.move_final:
        move_final()
        return
    
    # Escanear
    log("=" * 70)
    log("  PIPELINE CHD PSX — Escaneando...")
    log("=" * 70)
    missing = scan_missing()
    log(f"Total sem CHD: {len(missing)}")
    
    # Classificar
    converter, buscar_chd, ignorar = classify(missing)
    log(f"  Converter: {len(converter)}")
    log(f"  Buscar CHD: {len(buscar_chd)}")
    log(f"  Ignorar: {len(ignorar)}")
    
    total_gb = sum(i['total_size'] for i in converter) / 1024 / 1024 / 1024
    log(f"  Tamanho total fontes: {total_gb:.1f} GB")
    
    # Salvar listas
    with open(PSX_DIR / '_pipeline_converter.json', 'w', encoding='utf-8') as f:
        json.dump(converter, f, ensure_ascii=False, indent=2)
    with open(PSX_DIR / '_pipeline_buscar.json', 'w', encoding='utf-8') as f:
        json.dump(buscar_chd, f, ensure_ascii=False, indent=2)
    
    if args.list_only or args.dry_run:
        print(f"\n{'='*70}")
        print(f"  CONVERTER ({len(converter)} jogos)")
        print(f"{'='*70}")
        for i, item in enumerate(converter):
            size_mb = item['total_size'] / 1024 / 1024
            sr = item.get('serial') or '????'
            print(f"  [{i+1:3d}] {sr:12s} | {item['source_type']:10s} | {size_mb:8.1f}MB | {item['base_name'][:50]}")
        print(f"\n{'='*70}")
        print(f"  BUSCAR CHD PRONTO ({len(buscar_chd)} jogos)")
        print(f"{'='*70}")
        for i, item in enumerate(buscar_chd):
            sr = item.get('serial') or '????'
            print(f"  [{i+1:3d}] {sr:12s} | {item['source_type']:10s} | {item['base_name'][:60]}")
        return
    
    # Converter
    log(f"\nINICIANDO CONVERSAO: {len(converter)} jogos com {args.workers} workers")
    with _lock:
        _state["total"] = len(converter)
    
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(convert_one, item, i % args.workers): item for i, item in enumerate(converter)}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except Exception as e:
                log(f"EXC: {item['base_name']}: {e}")
                with _lock:
                    _state["failed"] += 1
    
    with _lock:
        s = dict(_state)
    log(f"\n{'='*70}")
    log(f"  CONVERSAO CONCLUIDA")
    log(f"  Total:     {s['total']}")
    log(f"  Convertidos: {s['converted']}")
    log(f"  Verificados: {s['verified']}")
    log(f"  Pulados:   {s['skipped']}")
    log(f"  Falhados:  {s['failed']}")
    log(f"  Erros:     {len(s['errors'])}")
    log(f"{'='*70}")
    
    # Mover CHDs para colecao
    if s['converted'] > 0 or s['skipped'] > 0:
        log("\nMovendo CHDs de F:\\chd_temp para colecao...")
        moved, failed = move_final()
        log(f"CHDs movidos: {moved}, falharam: {failed}")
    
    # Salvar lista de buscar_chd para proxima fase
    log(f"\nPROXIMO PASSO: buscar {len(buscar_chd)} CHDs prontos no archive.org")
    log(f"Lista salva em: _pipeline_buscar.json")


if __name__ == '__main__':
    main()
