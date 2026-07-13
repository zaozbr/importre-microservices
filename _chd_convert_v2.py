#!/usr/bin/env python3
"""Converte todos os ROMs PSX para CHD — versao 2.
Lista arquivos REAIS no disco, filtra os que ja tem CHD, e converte.
Suporta: .cue (multi-track), .bin (single-track), .iso, .img, .mdf, .ecm
ECM decodificado em Python nativo (sem unecm.exe).

Uso:
    python _chd_convert_v2.py              # converte tudo, 4 workers
    python _chd_convert_v2.py --workers 8  # 8 conversoes paralelas
    python _chd_convert_v2.py --dry-run    # so lista, nao converte
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import shutil
import tempfile
import psutil
from pathlib import Path
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ============================================================
# CONFIG
# ============================================================
PSX_DIR = Path(r"D:\roms\library\roms\psx")
DUP_DIR = Path(r"D:\roms\duplicados")  # duplicados e BINs movidos para re-download

# Importar helpers de conversao de formatos (CCD->CUE, MDF->BIN/CUE)
sys.path.insert(0, str(PSX_DIR))
from _ccd2cue import ccd_to_cue
from _mdf2cue import mdf_to_bin_cue, create_cue as create_simple_cue
CHD_OUTPUT_DIR = Path(r"F:\chd_temp")  # SSD temporario — copiar de volta ao final
CHDMAN = str(PSX_DIR / "chdman.exe")
PROGRESS_PATH = PSX_DIR / "_chd_convert_progress.json"
LOG_PATH = PSX_DIR / "_chd_convert.log"
LOCK_PATH = PSX_DIR / "_chd_convert.lock"
DASHBOARD_PORT = 8766

ROM_EXTS = {".bin", ".iso", ".img", ".mdf", ".ecm"}
INVALID_CHARS = '<>:"/\\|?*'

# ============================================================
# VERIFICACAO DE ARQUIVO PRONTO PARA CONVERSAO
# Evita converter arquivos ainda em download ou abertos pelo importre
# ============================================================
def _is_file_locked_windows(path):
    """Retorna True se outro processo tem o arquivo aberto (sharing violation)."""
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        GENERIC_READ = 0x80000000
        OPEN_EXISTING = 3
        FILE_SHARE_NONE = 0
        INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
        ERROR_SHARING_VIOLATION = 32

        handle = kernel32.CreateFileW(
            str(path),
            GENERIC_READ,
            FILE_SHARE_NONE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if handle == INVALID_HANDLE_VALUE:
            err = kernel32.GetLastError()
            return err == ERROR_SHARING_VIOLATION
        kernel32.CloseHandle(handle)
        return False
    except Exception:
        return False


def _has_download_temp_file(path):
    """Verifica se existe arquivo temporario de download (.part, .tmp, .crdownload etc)."""
    suffixes = (".part", ".tmp", ".crdownload", ".download", ".incomplete", ".unfinished")
    for suffix in suffixes:
        # arquivo com suffixo extra no nome (ex: jogo.bin.part)
        if path.with_suffix(path.suffix + suffix).exists():
            return True
        # arquivo com suffixo apos o nome completo (ex: jogo.bin.part)
        alt = path.parent / (path.name + suffix)
        if alt.exists():
            return True
    return False


def is_file_ready_for_conversion(path, stable_seconds=3, recent_seconds=60):
    """
    Verifica se o arquivo pode ser convertido sem interferir em um download.
    Retorna (ready: bool, reason: str).
    """
    path = Path(path)
    if not path.exists():
        return False, "arquivo nao existe"

    # 1. Arquivo temporario de download presente?
    if _has_download_temp_file(path):
        return False, "arquivo temporario de download encontrado"

    # 2. Se arquivo foi modificado recentemente, verificar se tamanho esta estavel
    try:
        mtime = path.stat().st_mtime
        age = time.time() - mtime
        if age < recent_seconds:
            s1 = path.stat().st_size
            time.sleep(stable_seconds)
            s2 = path.stat().st_size
            if s1 != s2:
                return False, f"tamanho mudando {s1} -> {s2} (download em andamento)"
    except Exception as e:
        return False, f"erro ao verificar tamanho: {e}"

    # 3. Arquivo aberto por outro processo?
    if _is_file_locked_windows(path):
        return False, "arquivo aberto por outro processo"

    return True, "ok"





def _normalize_stem_for_fuzzy(stem):
    s = stem
    # Serial com ou sem colchetes (ex: [SLPM-86728], SLPM-86728, SLPS-00785)
    s = re.sub(r'\[?[A-Z]{2,4}[-]\d{3,5}\]?', '', s)
    # Track (ex: Track 1 ou Track 01)
    s = re.sub(r'\(Track \d+\)', '', s, flags=re.I)
    # Versao (v1.0 ou 1.1a)
    s = re.sub(r'\(v?\d+(?:\.\d+)?(?:[a-z]?)\)', '', s, flags=re.I)
    # Regioes conhecidas entre parenteses
    regions = r'Japan|USA|Europe|Germany|France|Spain|Italy|Netherlands|Sweden|Australia|Korea|Brazil|Canada|World|United Kingdom|UK|Russia|China|Asia|En,Fr,De,Es,It|En,Fr,De|En,Fr|Fr,De|Ja,En|Fr,Es|De,Es|Multi|English|Japanese'
    s = re.sub(rf'\(({regions}|(?:[A-Za-z]{{2,8}}, )*[A-Za-z]{{2,8}})\)', '', s, flags=re.I)
    # Regioes de 1 letra (J, E, U) e combinacoes (ex: (J,E))
    single_regions = 'J|E|U|G|F|S|I|K|B|A|C|W|R|H|T|N|M|P'
    s = re.sub(rf'\((?:{single_regions})(?:,\s*(?:{single_regions}))*\)', '', s, flags=re.I)
    # Disc references (ex: (Disc 1), [Disc1of2], Disc1, Disc 1)
    s = re.sub(r'\(?\[?Disc\s*\d+(?:of\d+)?\]?\)?', '', s, flags=re.I)
    # Normalizar hifens para espacos (para comparacao)
    s = s.replace('-', ' ')
    # Limpar espacos e separadores residuais
    s = re.sub(r'\s+', ' ', s)
    return s.strip(' ._-\t\r\n')

def find_file_in_subdirs(name, base_dir=None, fuzzy=False):
    if base_dir is None:
        base_dir = PSX_DIR
    name = Path(name).name
    target_stem = _normalize_stem_for_fuzzy(Path(name).stem)
    if not target_stem:
        return None
    target_ext = Path(name).suffix.lower()
    exact_matches = []
    prefix_matches = []
    for root, _, files in os.walk(base_dir):
        for f in files:
            if f == name:
                return Path(root) / f
            if fuzzy:
                fp = Path(f)
                if fp.suffix.lower() != target_ext:
                    continue
                f_stem = _normalize_stem_for_fuzzy(fp.stem)
                if not f_stem:
                    continue
                if f_stem == target_stem:
                    exact_matches.append(Path(root) / f)
                elif f_stem.startswith(target_stem) or target_stem.startswith(f_stem):
                    prefix_matches.append((Path(root) / f, len(f_stem)))
    if exact_matches:
        return exact_matches[0]
    if prefix_matches:
        prefix_matches.sort(key=lambda x: (-x[1], str(x[0])))
        return prefix_matches[0][0]
    return None

def find_cue_for_bin_in_subdirs(bin_path):
    """Procura .cue correspondente ao .bin em PSX_DIR e subpastas."""
    bin_path = Path(bin_path)
    stem = bin_path.stem
    base = re.sub(r"\(Track \d+\)", "", stem, flags=re.I).strip()
    for name in [stem + ".cue", base + ".cue"]:
        found = find_file_in_subdirs(name)
        if found:
            return found
    return None


def acquire_lock():
    """Cria lock file; retorna True se conseguiu, False se outra instancia esta rodando."""
    try:
        if LOCK_PATH.exists():
            try:
                pid = int(LOCK_PATH.read_text(encoding="utf-8").strip())
                if pid != os.getpid() and psutil.Process(pid).is_running():
                    # Verificar se e realmente o conversor CHD
                    cmd = " ".join(psutil.Process(pid).cmdline() or [])
                    if "_chd_convert_v2.py" in cmd:
                        return False
            except Exception:
                pass
        LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except Exception:
        return False

def release_lock():
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass

# ============================================================
# ESTADO COMPARTILHADO
# ============================================================
_lock = threading.Lock()
_state = {
    "total": 0,
    "completed": 0,
    "failed": 0,
    "skipped": 0,
    "in_progress": {},
    "queue": [],
    "errors": [],
    "start_time": None,
    "workers": 4,
    "log_lines": [],
}

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _lock:
        _state["log_lines"].append(line)
        if len(_state["log_lines"]) > 200:
            _state["log_lines"] = _state["log_lines"][-200:]
    try:
        # Reconfigurar stdout para UTF-8 (evita OSError [Errno 22] em caracteres especiais no Windows)
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(line, flush=True)
    except Exception:
        try:
            # Fallback: escrever bytes diretamente
            sys.stdout.buffer.write(line.encode(sys.stdout.encoding or "utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")
            sys.stdout.buffer.flush()
        except Exception:
            pass
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def save_state():
    try:
        with _lock:
            data = {
                "total": _state["total"],
                "completed": _state["completed"],
                "failed": _state["failed"],
                "skipped": _state["skipped"],
                "start_time": _state["start_time"],
                "workers": _state["workers"],
                "queue_len": len(_state["queue"]),
                "in_progress": dict(_state["in_progress"]),
                "log_lines": list(_state["log_lines"][-50:]),
                "errors": list(_state["errors"][-30:]),
                "timestamp": time.time(),
            }
        # Escrita direta (sem .tmp — evita PermissionError no Windows)
        with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        pass  # nao fatal

def sanitize_filename(name):
    for c in INVALID_CHARS:
        name = name.replace(c, "")
    if len(name) > 180:
        name = name[:180]
    return name.strip().rstrip(".")

def build_chd_name(serial, name):
    base = name
    # Homebrew: HBREW/HOMEBREW nao sao seriais reais, apenas referencia
    is_homebrew = serial and serial.startswith(("HBREW", "HOMEBREW"))
    # Remover serial do nome se ja estiver la
    if serial and not is_homebrew:
        base = re.sub(r"[\-_]?\s*" + re.escape(serial), "", base, flags=re.I)
        # Tambem remover sem zero-pad
        serial_nodash = serial.replace("-", "")
        base = re.sub(r"[\-_]?\s*" + serial_nodash, "", base, flags=re.I)
    base = re.sub(r"\(Disc \d+\)", "", base, flags=re.I).strip()
    base = re.sub(r"\(Track \d+\)", "", base, flags=re.I).strip()
    base = re.sub(r"\(.*?\)", "", base).strip()
    base = re.sub(r"[^\w\s-]", "", base)
    base = re.sub(r"\s+", "-", base)
    base = re.sub(r"-+", "-", base)
    base = base.strip("-")
    if serial and not is_homebrew:
        base = f"{base}-{serial}"
    return sanitize_filename(base) + ".chd"

def extract_serial(filename):
    m = re.search(r"(SLUS|SLES|SCES|SLPS|SLPM|SCPS|SCUS|SLKA|SCED|SIPS|PAPX|SLED|PCPX|PBPX|SCZS|SCPM|ESPM|PUPX|PTPX|PEPX|SCAJ|PCPD|PSRM|NYMC)[-_]?(\d{4,5})", filename, re.I)
    if m:
        return f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
    return ""

def decode_ecm(ecm_path, out_path):
    """Decodifica ECM para BIN usando unecm.exe nativo (compilado de kidoz/ecm v1.3.1).
    Fallback para decoder Python se unecm.exe nao existir.
    """
    unecm = str(PSX_DIR / "unecm.exe")
    if os.path.exists(unecm):
        try:
            result = subprocess.run(
                [unecm, str(ecm_path), str(out_path)],
                capture_output=True, text=True, timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode == 0 and out_path.exists():
                return True, "ok (unecm.exe)"
            return False, f"unecm falhou: {result.stderr[:200]}"
        except Exception as e:
            return False, str(e)
    # Fallback: decoder Python (lento)
    return _decode_ecm_python(ecm_path, out_path)


def _decode_ecm_python(ecm_path, out_path):
    """Decoder ECM em Python puro — fallback lento se unecm.exe nao existir."""
    # Inicializar LUTs de ECC/EDC
    ecc_f_lut = [0] * 256
    ecc_b_lut = [0] * 256
    edc_lut = [0] * 256
    for i in range(256):
        j = (i << 1) ^ (0x11D if (i & 0x80) else 0)
        ecc_f_lut[i] = j & 0xFF
        ecc_b_lut[i ^ j] = i
        edc = i
        for _ in range(8):
            edc = (edc >> 1) ^ (0xD8018001 if (edc & 1) else 0)
        edc_lut[i] = edc & 0xFFFFFFFF

    def edc_partial(edc, src):
        for b in src:
            edc = (edc >> 8) ^ edc_lut[(edc ^ b) & 0xFF]
        return edc & 0xFFFFFFFF

    def edc_compute(src, size):
        edc = edc_partial(0, src[:size])
        return bytes([(edc >> 0) & 0xFF, (edc >> 8) & 0xFF, (edc >> 16) & 0xFF, (edc >> 24) & 0xFF])

    def ecc_compute_block(src, major_count, minor_count, major_mult, minor_inc):
        size = major_count * minor_count
        dest = [0] * (major_count * 2)
        for major in range(major_count):
            index = (major >> 1) * major_mult + (major & 1)
            ecc_a = 0
            ecc_b = 0
            for minor in range(minor_count):
                temp = src[index]
                index += minor_inc
                if index >= size:
                    index -= size
                ecc_a ^= temp
                ecc_b ^= temp
                ecc_a = ecc_f_lut[ecc_a]
            ecc_a = ecc_b_lut[ecc_f_lut[ecc_a] ^ ecc_b]
            dest[major] = ecc_a
            dest[major + major_count] = ecc_a ^ ecc_b
        return bytes(dest)

    def ecc_generate(sector, zeroaddress):
        if zeroaddress:
            addr = sector[12:16]
            sector[12:16] = b'\x00\x00\x00\x00'
        # ECC P
        p = ecc_compute_block(sector[0xC:], 86, 24, 2, 86)
        sector[0x81C:0x81C+172] = p
        # ECC Q
        q = ecc_compute_block(sector[0xC:], 52, 43, 86, 88)
        sector[0x8C8:0x8C8+104] = q
        if zeroaddress:
            sector[12:16] = addr

    def eccedc_generate(sector, dtype):
        if dtype == 1:  # Mode 1
            edc = edc_compute(sector, 0x810)
            sector[0x810:0x814] = edc
            sector[0x814:0x81C] = b'\x00' * 8
            ecc_generate(sector, 0)
        elif dtype == 2:  # Mode 2 form 1
            edc = edc_compute(sector[0x10:], 0x808)
            sector[0x818:0x81C] = edc
            ecc_generate(sector, 1)
        elif dtype == 3:  # Mode 2 form 2
            edc = edc_compute(sector[0x10:], 0x91C)
            sector[0x92C:0x930] = edc

    try:
        with open(ecm_path, "rb") as fin, open(out_path, "wb") as fout:
            header = fin.read(4)
            if header != b"ECM\x00":
                return False, "header ECM invalido"
            checkedc = 0
            while True:
                c = fin.read(1)
                if not c:
                    break
                c = c[0]
                dtype = c & 3
                num = (c >> 2) & 0x1F
                bits = 5
                while c & 0x80:
                    c = fin.read(1)
                    if not c:
                        return False, "EOF inesperado em num"
                    c = c[0]
                    num |= (c & 0x7F) << bits
                    bits += 7
                if num == 0xFFFFFFFF:
                    break
                num += 1
                if num >= 0x80000000:
                    return False, "num muito grande"
                if dtype == 0:
                    # Raw — copiar direto
                    remaining = num
                    while remaining > 0:
                        b = min(remaining, 2352)
                        data = fin.read(b)
                        if len(data) < b:
                            return False, "dados truncados (raw)"
                        checkedc = edc_partial(checkedc, data)
                        fout.write(data)
                        remaining -= b
                else:
                    for _ in range(num):
                        sector = bytearray(2352)
                        sector[1:11] = b'\xFF' * 10
                        if dtype == 1:  # Mode 1
                            sector[0x0F] = 0x01
                            data = fin.read(0x003)
                            if len(data) < 3:
                                return False, "dados truncados (mode1 addr)"
                            sector[0x00C:0x00F] = data
                            data = fin.read(0x800)
                            if len(data) < 0x800:
                                return False, "dados truncados (mode1 data)"
                            sector[0x010:0x810] = data
                            eccedc_generate(sector, 1)
                            checkedc = edc_partial(checkedc, bytes(sector))
                            fout.write(bytes(sector))
                        elif dtype == 2:  # Mode 2 form 1
                            sector[0x0F] = 0x02
                            data = fin.read(0x804)
                            if len(data) < 0x804:
                                return False, "dados truncados (mode2f1)"
                            sector[0x014:0x818] = data
                            sector[0x10:0x14] = sector[0x14:0x18]
                            eccedc_generate(sector, 2)
                            checkedc = edc_partial(checkedc, bytes(sector[0x10:0x930+0x10]))
                            fout.write(bytes(sector[0x10:0x930+0x10]))
                        elif dtype == 3:  # Mode 2 form 2
                            sector[0x0F] = 0x02
                            data = fin.read(0x918)
                            if len(data) < 0x918:
                                return False, "dados truncados (mode2f2)"
                            sector[0x014:0x92C] = data
                            sector[0x10:0x14] = sector[0x14:0x18]
                            eccedc_generate(sector, 3)
                            checkedc = edc_partial(checkedc, bytes(sector[0x10:0x930+0x10]))
                            fout.write(bytes(sector[0x10:0x930+0x10]))
            # Verificar EDC final
            tail = fin.read(4)
            if len(tail) == 4:
                expected = (tail[3] << 24) | (tail[2] << 16) | (tail[1] << 8) | tail[0]
                if expected != checkedc:
                    log(f"ECM EDC mismatch (pode ser ok)")
        return True, "ok"
    except Exception as e:
        return False, str(e)

_cue_files_cache = None

def _build_cue_cache():
    global _cue_files_cache
    if _cue_files_cache is None:
        _cue_files_cache = {}
        for f in sorted(PSX_DIR.glob('*.cue')):
            _cue_files_cache.setdefault(f.name, f)
        for f in sorted(PSX_DIR.rglob('*.cue')):
            _cue_files_cache.setdefault(f.name, f)
    return _cue_files_cache

def find_cue_for_bin(bin_path, use_cache=True):
    bin_path = Path(bin_path)
    stem = bin_path.stem
    base = re.sub(r"\(Track \d+\)", '', stem, flags=re.I).strip()
    for name in [base + '.cue', stem + '.cue']:
        if use_cache:
            cache = _build_cue_cache()
            if name in cache:
                return cache[name]
        else:
            found = find_file_in_subdirs(name)
            if found:
                return found
    return None

def rename_failed_source(filepath, serial, name):
    """Renomeia arquivos fonte de uma conversao falha para [nome][serial]-nao-conversivel.*
    Mantem os arquivos no mesmo diretorio. Retorna lista de arquivos renomeados."""
    filepath = Path(filepath)
    renamed = []
    # Se ja tem -nao-conversivel no nome, nao renomear de novo
    if "nao-conversivel" in filepath.name.lower():
        return []
    # Base do nome: [nome][serial]-nao-conversivel
    base_name = ""
    if name:
        # Limpar nome
        clean = re.sub(r'[<>:"/\\|?*]', '', name)
        clean = re.sub(r'\s+', ' ', clean).strip()
        base_name = clean[:60]
    if serial:
        base_name = f"{base_name}[{serial}]"
    base_name = f"{base_name}-nao-conversivel"
    base_name = sanitize_filename(base_name)

    # Renomear o arquivo principal
    if filepath.exists():
        new_path = filepath.parent / f"{base_name}{filepath.suffix}"
        try:
            if new_path.exists():
                new_path.unlink()
            filepath.rename(new_path)
            renamed.append(new_path)
        except Exception as e:
            log(f"rename_failed: erro ao renomear {filepath.name}: {e}")

    # Renomear arquivos companheiros (mesmo stem, extensoes diferentes)
    for ext in ['.cue', '.bin', '.img', '.iso', '.mdf', '.ecm', '.ccd', '.sub', '.mds']:
        companion = filepath.with_suffix(ext)
        if companion.exists() and companion != filepath:
            new_companion = filepath.parent / f"{base_name}{ext}"
            try:
                if new_companion.exists():
                    new_companion.unlink()
                companion.rename(new_companion)
                renamed.append(new_companion)
            except Exception:
                pass

    # Para multi-track: renomear todos os tracks com mesmo base
    parent = filepath.parent
    stem_base = re.sub(r'\s*\(Track\s*\d+\)\s*$', '', filepath.stem, flags=re.I)
    if stem_base != filepath.stem:
        for f in parent.glob(f"{stem_base}*"):
            if f.is_file() and f != filepath and f.stem.startswith(stem_base):
                track_suffix = re.search(r'\(Track\s*\d+\)', f.name, re.I)
                track_str = track_suffix.group(0) if track_suffix else ""
                new_f = parent / f"{base_name}{track_str}{f.suffix}"
                try:
                    if new_f.exists():
                        new_f.unlink()
                    f.rename(new_f)
                    renamed.append(new_f)
                except Exception:
                    pass

    return renamed


def add_failed_to_importre(serial, name, reason=""):
    """Adiciona um item falho à fila do importre para re-download,
    com flag _search_chd para indicar que deve procurar direto pelo .chd."""
    try:
        sys.path.insert(0, str(PSX_DIR))
        from importre import file_lock, file_unlock, load_json, save_json, QUEUE_PATH
        fl = file_lock()
        try:
            data = load_json(QUEUE_PATH, {})
            existing = set()
            for q in data.get("queue", []):
                if q.get("serial"):
                    existing.add(q["serial"].upper())
            for k in data.get("in_progress", {}).keys():
                existing.add(k.upper())
            for k in data.get("completed", {}).keys():
                existing.add(k.upper())
            for k in data.get("failed", {}).keys():
                existing.add(k.upper())

            s = (serial or "").upper()
            if s and s in existing:
                # Ja esta na fila — atualizar flags
                for q in data.get("queue", []):
                    if q.get("serial", "").upper() == s:
                        q["_search_chd"] = True
                        q["_convert_failed"] = True
                        q["_fail_reason"] = reason[:200]
                        break
            else:
                data["queue"].append({
                    "serial": serial or "",
                    "name": name or "",
                    "region": "",
                    "section": "",
                    "type": "commercial",
                    "_needs_search": True,
                    "_search_chd": True,
                    "_convert_failed": True,
                    "_fail_reason": reason[:200],
                })
            data["total"] = len(data.get("queue", [])) + len(data.get("in_progress", {})) + len(data.get("completed", {})) + len(data.get("failed", {}))
            save_json(QUEUE_PATH, data)
        finally:
            file_unlock(fl)
        log(f"  -> Adicionado ao importre com _search_chd=true: {serial or name}")
    except Exception as e:
        log(f"  -> Erro ao adicionar ao importre: {e}")


def safe_remove(path, retries=5, delay=1.0):
    """Remove arquivo com retry para evitar WinError 32 (arquivo em uso)."""
    for i in range(retries):
        try:
            if path and Path(path).exists():
                Path(path).unlink()
            return True
        except Exception:
            time.sleep(delay)
    return False

def safe_move(src, dst, retries=5, delay=1.0):
    """Move arquivo com retry para evitar WinError 32."""
    for i in range(retries):
        try:
            if Path(dst).exists():
                Path(dst).unlink()
            shutil.move(str(src), str(dst))
            return True
        except Exception:
            time.sleep(delay)
    # Ultima tentativa: copiar + deletar
    try:
        shutil.copy2(str(src), str(dst))
        safe_remove(src)
        return True
    except Exception:
        return False

def generate_cue_for_bin(bin_path, cue_path=None):
    """Gera um CUE simples MODE2/2352 para um BIN single-track (PSX)."""
    if cue_path is None:
        cue_path = Path(bin_path).with_suffix(".cue")
    bin_name = Path(bin_path).name
    with open(cue_path, "w", encoding="utf-8") as f:
        f.write(f'FILE "{bin_name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
    return cue_path


def _has_non_ascii(s):
    return any(ord(c) > 127 for c in s)


def _ascii_stem(stem):
    """Sanitiza um stem para nome de arquivo ASCII seguro."""
    out = []
    for c in stem:
        if ord(c) > 127:
            out.append("_")
        elif c in INVALID_CHARS:
            out.append("")
        else:
            out.append(c)
    base = "".join(out).strip().rstrip(".")
    base = re.sub(r"\s+", "_", base)
    base = re.sub(r"_+", "_", base)
    return base[:120]


def _find_fuzzy_cue_ref(ref):
    """Procura em PSX_DIR e DUP_DIR por arquivo .bin/.img/.iso/.mdf/.ecm cujo
    stem normalizado seja exato, prefixo ou muito similar ao stem de ref."""
    ref_path = Path(ref)
    target_stem = _normalize_stem_for_fuzzy(ref_path.stem).lower()
    if not target_stem:
        return None
    target_ext = ref_path.suffix.lower()
    allowed = ROM_EXTS
    # Diretorios de busca: apenas PSX_DIR (DUP_DIR nao conta mais)
    search_dirs = [PSX_DIR]

    # Estrategia 1: match exato do filename em toda a arvore
    for d in search_dirs:
        for f in d.rglob(ref_path.name):
            if f.is_file() and f.suffix.lower() in allowed:
                return f

    # Estrategia 2: match com serial removido mas track mantido
    def _remove_serial_only(stem):
        s = re.sub(r'\[?[A-Z]{2,4}[-]\d{3,5}\]?', '', stem)
        s = re.sub(r'\s+', ' ', s)
        return s.strip(' ._-\t\r\n').lower()

    ref_no_serial = _remove_serial_only(ref_path.stem)
    if ref_no_serial:
        for d in search_dirs:
            for f in d.rglob('*'):
                if not f.is_file():
                    continue
                ext = f.suffix.lower()
                if ext not in allowed:
                    continue
                f_no_serial = _remove_serial_only(f.stem)
                if f_no_serial and f_no_serial == ref_no_serial:
                    # Preferir extensao igual
                    if target_ext and ext == target_ext:
                        return f
        # Se encontrou match sem serial mas com track, retornar o melhor
        # (ja retornado acima se extensao bateu)

    # Estrategia 3: fuzzy sem track (comportamento original)
    import difflib
    best = None
    best_score = 0.0
    for d in search_dirs:
        for f in d.rglob('*'):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in allowed:
                continue
            f_stem = _normalize_stem_for_fuzzy(f.stem).lower()
            if not f_stem:
                continue
            if f_stem == target_stem:
                if target_ext and ext == target_ext:
                    return f
                best = f
                best_score = 1.0
                continue
            if f_stem.startswith(target_stem) or target_stem.startswith(f_stem):
                score = 0.9
            else:
                score = difflib.SequenceMatcher(None, target_stem, f_stem).ratio()
            if target_ext and ext == target_ext:
                score += 0.01
            if score > best_score:
                best_score = score
                best = f
    if best and best_score >= 0.85:
        return best
    return None


def _merge_duplicate_file_refs(content):
    """Fundir declaracoes FILE duplicadas no CUE.
    Alguns CUEs tem um FILE por track apontando para o mesmo BIN.
    chdman precisa de apenas um FILE com todas as TRACKs dentro."""
    lines = content.splitlines()
    seen_files = set()
    output = []
    for line in lines:
        stripped = line.strip()
        # Detectar linha FILE
        m = re.match(r'FILE\s+"([^"]+)"\s+\w+', stripped, re.I)
        if m:
            fname = m.group(1).lower()
            if fname in seen_files:
                # Skip duplicate FILE line
                continue
            seen_files.add(fname)
        output.append(line)
    return "\n".join(output) + "\n"


def prepare_cue_for_chdman(cue_path, worker_id=None):
    """
    Resolve referencias de um CUE que apontam para arquivos ausentes no mesmo diretorio.
    Procura em subpastas de PSX_DIR (exata + fuzzy), copia os arquivos para CHD_OUTPUT_DIR
    junto com o CUE reescrito. Retorna (novo_cue_path, arquivos_temporarios) ou None
    se alguma referencia nao puder ser resolvida.
    """
    CHD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cue_path = Path(cue_path)
    cue_dir = cue_path.parent
    content = cue_path.read_text(encoding="utf-8", errors="replace")
    # Corrigir BINARY BINARY duplicado
    content = re.sub(r'BINARY\s+BINARY', 'BINARY', content, flags=re.I)
    # Corrigir MOTOROLA MOTOROLA duplicado
    content = re.sub(r'MOTOROLA\s+MOTOROLA', 'MOTOROLA', content, flags=re.I)
    # Corrigir WAV WAV duplicado
    content = re.sub(r'WAV\s+WAV', 'WAV', content, flags=re.I)
    # Corrigir MP3 MP3 duplicado
    content = re.sub(r'MP3\s+MP3', 'MP3', content, flags=re.I)
    # Corrigir AIFF AIFF duplicado
    content = re.sub(r'AIFF\s+AIFF', 'AIFF', content, flags=re.I)
    # Fundir FILEs duplicados (mesmo arquivo referenciado em multiplos FILEs)
    content = _merge_duplicate_file_refs(content)
    file_refs = re.findall(r'FILE\s+"([^"]+)"', content)
    temp_files = []
    new_content = content
    # Sempre criar CUE temporario em CHD_OUTPUT_DIR para garantir caminhos curtos/ASCII
    new_cue = CHD_OUTPUT_DIR / f"_cue_{_ascii_stem(cue_path.stem)}_{worker_id or 0}.cue"
    has_refs = False
    for ref in file_refs:
        has_refs = True
        ref_path = cue_dir / ref
        if ref_path.exists():
            real_path = ref_path
        else:
            # Procurar em toda a arvore PSX_DIR por arquivo .bin/.img/.iso/.mdf/.ecm
            # cujo stem seja similar ao stem do arquivo referenciado
            real_path = _find_fuzzy_cue_ref(ref)
            if not real_path and ref.lower().endswith('.bin'):
                # Tentar ECM correspondente (ex: .bin referenciado mas so existe .ecm)
                ecm_ref = ref[:-4] + '.ecm'
                real_path = _find_fuzzy_cue_ref(ecm_ref)
        if not real_path or not real_path.exists():
            log(f"[W{worker_id}] CUE ref nao encontrada: {ref} em {cue_path.name}")
            return None
        # Arquivo ECM precisa ser decodificado antes de ser usado pelo chdman
        if real_path.suffix.lower() == '.ecm':
            bin_out = CHD_OUTPUT_DIR / f"{_ascii_stem(real_path.stem)}_{worker_id or 0}.bin"
            ok, msg = decode_ecm(real_path, bin_out)
            if ok and bin_out.exists():
                temp_files.append(bin_out)
                new_content = new_content.replace(f'"{ref}"', f'"{bin_out.name}"')
                continue
            log(f"[W{worker_id}] ECM decode falhou para CUE ref {ref}: {msg}")
            return None
        # Copiar/criar link para CHD_OUTPUT_DIR
        dest = CHD_OUTPUT_DIR / real_path.name
        if dest.exists() and dest.resolve() != real_path.resolve():
            dest = CHD_OUTPUT_DIR / f"{_ascii_stem(real_path.stem)}_{worker_id or 0}{real_path.suffix}"
        try:
            if dest.exists():
                safe_remove(dest)
            try:
                os.link(str(real_path), str(dest))
            except OSError:
                shutil.copy2(str(real_path), str(dest))
        except Exception as e:
            log(f"[W{worker_id}] Erro ao copiar {real_path.name} para {dest}: {e}")
            return None
        temp_files.append(dest)
        new_content = new_content.replace(f'"{ref}"', f'"{dest.name}"')
    if has_refs and temp_files:
        new_cue.write_text(new_content, encoding="utf-8")
        temp_files.append(new_cue)
        return new_cue, temp_files
    return cue_path, temp_files


def make_ascii_input(input_file, worker_id=None):
    """
    chdman createcd nao suporta caminhos com caracteres nao-ASCII no Windows.
    Copia o arquivo de entrada (e companheiros referenciados por CUE) para um
    caminho ASCII temporario em CHD_OUTPUT_DIR. Retorna (novo_input, arquivos_temporarios).
    """
    input_file = Path(input_file)
    if not _has_non_ascii(str(input_file)):
        return input_file, []

    temp_files = []
    suffix = input_file.suffix.lower()

    # Copiar arquivo principal
    new_stem = _ascii_stem(input_file.stem)
    temp_main = CHD_OUTPUT_DIR / (new_stem + suffix)
    shutil.copy2(str(input_file), str(temp_main))
    temp_files.append(temp_main)

    if suffix != ".cue":
        return temp_main, temp_files

    # Para CUE, copiar todos os arquivos referenciados e reescrever o CUE
    cue_dir = input_file.parent
    content = input_file.read_text(encoding="utf-8", errors="replace")
    file_refs = re.findall(r'FILE\s+"([^"]+)"', content)
    mapping = {}
    missing = []
    for ref in file_refs:
        ref_path = cue_dir / ref
        if not ref_path.exists():
            # Procurar em subpastas de PSX_DIR (ex: duplicados)
            ref_path = find_file_in_subdirs(ref)
        if not ref_path or not ref_path.exists():
            missing.append(ref)
            continue
        ref_stem = _ascii_stem(Path(ref).stem)
        ref_new_name = ref_stem + Path(ref).suffix
        temp_ref = CHD_OUTPUT_DIR / ref_new_name
        shutil.copy2(str(ref_path), str(temp_ref))
        temp_files.append(temp_ref)
        mapping[ref] = ref_new_name

    if missing:
        raise FileNotFoundError(f"CUE referencia arquivos nao encontrados: {missing}")

    # Reescrever CUE com novos nomes
    new_content = content
    for old, new in mapping.items():
        new_content = new_content.replace(f'"{old}"', f'"{new}"')
    temp_main.write_text(new_content, encoding="utf-8")
    return temp_main, temp_files

def prepare_img_ccd(img_path):
    """Converte CCD+IMG+SUB para CUE. Retorna Path do .cue gerado ou None.
    O CUE e gerado no mesmo diretorio do .img (PSX_DIR) para que o chdman
    encontre o arquivo de imagem referenciado."""
    ccd_path = img_path.with_suffix(".ccd")
    if not ccd_path.exists():
        return None
    cue_content = ccd_to_cue(ccd_path, img_path.name)
    if not cue_content:
        return None
    cue_path = img_path.with_suffix(".cue")
    cue_path.write_text(cue_content, encoding="utf-8")
    return cue_path

def prepare_mdf(mdf_path):
    """Converte MDF (com ou sem MDS) para BIN/CUE. Retorna (bin_path, cue_path) ou None."""
    result = mdf_to_bin_cue(mdf_path, CHD_OUTPUT_DIR)
    if result:
        return result
    return None

def chd_exists_anywhere(chd_name):
    """Verifica se CHD ja existe em PSX_DIR ou em CHD_OUTPUT_DIR (SSD temporario).
    NAO checa DUP_DIR — esses arquivos nao contam na colecao."""
    dirs = [PSX_DIR, CHD_OUTPUT_DIR]
    for d in dirs:
        p = d / chd_name
        if p.exists() and p.stat().st_size > 1024:
            return True
    return False

def convert_one(item, worker_id):
    """Converte um item para CHD."""
    serial = item.get("serial", "")
    name = item.get("name", "")
    filepath = Path(item["file"])
    ext = item.get("ext", filepath.suffix.lower())
    chd_name = build_chd_name(serial, name) if serial or name else sanitize_filename(filepath.stem) + ".chd"
    chd_path = CHD_OUTPUT_DIR / chd_name  # CHD final no SSD temporario

    # Garantir diretorio de saida no SSD
    CHD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Remover CHD invalido (tamanho 0) de execucao anterior interrompida
    if chd_path.exists() and chd_path.stat().st_size < 1024:
        safe_remove(chd_path)

    # Skip se CHD ja existe em qualquer lugar
    if chd_exists_anywhere(chd_name):
        log(f"[W{worker_id}] SKIP {chd_name} (ja existe)")
        with _lock:
            _state["skipped"] += 1
        return "skipped"

    if not filepath.exists():
        log(f"[W{worker_id}] FAIL {serial}: arquivo nao existe: {filepath.name}")
        add_failed_to_importre(serial, name, "arquivo nao existe")
        with _lock:
            _state["failed"] += 1
            _state["errors"].append(f"{serial}: arquivo nao existe: {filepath.name}")
        return "failed"

    # Verificar se arquivo esta pronto (download completo e nao aberto pela outra IA)
    ready, reason = is_file_ready_for_conversion(filepath)
    if not ready:
        log(f"[W{worker_id}] NOT READY {serial}: {filepath.name} — {reason}")
        return "not_ready"

    with _lock:
        _state["in_progress"][serial or filepath.stem] = {
            "name": name or filepath.stem,
            "file": filepath.name,
            "chd": chd_name,
            "start_time": time.time(),
            "worker": worker_id,
        }
    save_state()

    NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    temp_bin = None
    temp_cue = None
    temp_cue_img = None  # CUE auto-gerado para .img/.mdf
    temp_mdf_bin = None  # BIN gerado de MDF
    temp_files = []  # arquivos temporarios extras (ex: CUE preparado com bins de subpastas)
    temp_ascii_files = []  # arquivos temporarios criados por make_ascii_input

    try:
        if ext == ".ecm":
            # Decodificar ECM para BIN temporario (.bin, nao .bin.tmp — chdman nao reconhece .tmp)
            temp_bin = PSX_DIR / (filepath.stem + ".bin")
            log(f"[W{worker_id}] ECM decode: {filepath.name}")
            ok, msg = decode_ecm(filepath, temp_bin)
            if not ok or not temp_bin.exists():
                log(f"[W{worker_id}] FAIL {serial}: ECM decode falhou: {msg}")
                rename_failed_source(filepath, serial, name)
                add_failed_to_importre(serial, name, f"ECM decode: {msg}")
                with _lock:
                    _state["failed"] += 1
                    _state["errors"].append(f"{serial}: ECM decode: {msg}")
                return "failed"
            input_file = temp_bin
            # Verificar se tem CUE
            cue = find_cue_for_bin(filepath.with_suffix(".bin"))
            if cue and cue.exists():
                input_file = cue
                log(f"[W{worker_id}] CHD convert (ECM+cue): {cue.name} -> {chd_name}")
            else:
                # Gerar CUE automatico (MODE2/2352 — padrao PSX)
                temp_cue = PSX_DIR / (filepath.stem + ".cue")
                generate_cue_for_bin(temp_bin, temp_cue)
                input_file = temp_cue
                log(f"[W{worker_id}] CHD convert (ECM+auto-cue): {temp_cue.name} -> {chd_name}")
        elif ext == ".cue":
            input_file = filepath
            log(f"[W{worker_id}] CHD convert (cue): {filepath.name} -> {chd_name}")
        elif ext == ".bin":
            cue = find_cue_for_bin(filepath)
            if cue:
                input_file = cue
                log(f"[W{worker_id}] CHD convert (bin+cue): {cue.name} -> {chd_name}")
            else:
                # chdman createcd precisa de CUE para .bin isolado
                temp_cue = filepath.with_suffix(".cue")
                generate_cue_for_bin(filepath, temp_cue)
                input_file = temp_cue
                log(f"[W{worker_id}] CHD convert (bin+auto-cue): {temp_cue.name} -> {chd_name}")
        elif ext == ".img":
            # chdman nao entende CCD/MDS diretamente; converter para CUE/BIN
            cue = filepath.with_suffix(".cue")
            if cue.exists():
                input_file = cue
                log(f"[W{worker_id}] CHD convert (img+cue): {cue.name} -> {chd_name}")
            else:
                temp_cue_img = prepare_img_ccd(filepath)
                if temp_cue_img:
                    input_file = temp_cue_img
                    log(f"[W{worker_id}] CHD convert (img+ccd->cue): {temp_cue_img.name} -> {chd_name}")
                else:
                    temp_cue_img = filepath.with_suffix(".cue")
                    generate_cue_for_bin(filepath, temp_cue_img)
                    input_file = temp_cue_img
                    log(f"[W{worker_id}] CHD convert (img+auto-cue): {temp_cue_img.name} -> {chd_name}")
        elif ext == ".mdf":
            # chdman nao entende MDS diretamente; converter MDF para BIN/CUE
            cue = filepath.with_suffix(".cue")
            if cue.exists():
                input_file = cue
                log(f"[W{worker_id}] CHD convert (mdf+cue): {cue.name} -> {chd_name}")
            else:
                mdf_result = prepare_mdf(filepath)
                if mdf_result:
                    temp_mdf_bin, temp_cue_img = mdf_result
                    input_file = temp_cue_img
                    log(f"[W{worker_id}] CHD convert (mdf->bin/cue): {temp_cue_img.name} -> {chd_name}")
                else:
                    temp_cue_img = filepath.with_suffix(".cue")
                    generate_cue_for_bin(filepath, temp_cue_img)
                    input_file = temp_cue_img
                    log(f"[W{worker_id}] CHD convert (mdf+auto-cue): {temp_cue_img.name} -> {chd_name}")
        elif ext == ".iso":
            input_file = filepath
            log(f"[W{worker_id}] CHD convert (iso): {filepath.name} -> {chd_name}")
        else:
            input_file = filepath
            log(f"[W{worker_id}] CHD convert ({ext}): {filepath.name} -> {chd_name}")

        # Resolver CUEs que referenciam arquivos em subpastas (ex: duplicados)
        if str(input_file).lower().endswith(".cue"):
            temp_cue_prepared = prepare_cue_for_chdman(input_file, worker_id)
            if temp_cue_prepared:
                input_file, temp_files = temp_cue_prepared
                temp_files = list(temp_files) if temp_files else []

        # Validar CUE/BIN antes de passar ao chdman (CUE corrompido ou BIN sem alinhamento de setor trava chdman)
        if str(input_file).lower().endswith(".cue"):
            try:
                with open(input_file, "rb") as cf:
                    head = cf.read(100)
                if head == b"\x00" * len(head) or len(head) == 0:
                    log(f"[W{worker_id}] FAIL {serial}: CUE corrompido (zeros): {Path(input_file).name}")
                    rename_failed_source(filepath, serial, name)
                    add_failed_to_importre(serial, name, "CUE corrompido (zeros)")
                    with _lock:
                        _state["failed"] += 1
                        _state["errors"].append(f"{serial}: CUE corrompido (zeros)")
                    return "failed"
                if b"FILE" not in head:
                    with open(input_file, "r", encoding="utf-8", errors="replace") as cf:
                        content = cf.read(300)
                    if "FILE" not in content and "TRACK" not in content:
                        log(f"[W{worker_id}] FAIL {serial}: CUE sem estrutura FILE/TRACK: {Path(input_file).name}")
                        rename_failed_source(filepath, serial, name)
                        add_failed_to_importre(serial, name, "CUE sem estrutura")
                        with _lock:
                            _state["failed"] += 1
                            _state["errors"].append(f"{serial}: CUE sem estrutura")
                        return "failed"
            except Exception as e:
                log(f"[W{worker_id}] FAIL {serial}: erro ao ler CUE: {e}")
                rename_failed_source(filepath, serial, name)
                add_failed_to_importre(serial, name, f"erro CUE: {e}")
                with _lock:
                    _state["failed"] += 1
                    _state["errors"].append(f"{serial}: erro CUE: {e}")
                return "failed"
        # BIN single-track sem CUE: validar tamanho alinhado a setor (2352 ou 2048)
        if str(input_file).lower().endswith(".bin") and not find_cue_for_bin(Path(input_file)):
            sz = Path(input_file).stat().st_size
            if sz % 2352 != 0 and sz % 2048 != 0:
                log(f"[W{worker_id}] FAIL {serial}: BIN nao alinhado a setor (2352/2048): {Path(input_file).name} ({sz%2352}/{sz%2048})")
                rename_failed_source(filepath, serial, name)
                add_failed_to_importre(serial, name, "BIN nao alinhado a setor")
                with _lock:
                    _state["failed"] += 1
                    _state["errors"].append(f"{serial}: BIN nao alinhado a setor")
                return "failed"

        # chdman createcd nao suporta caracteres nao-ASCII no caminho do input
        # no Windows. Copiar para um caminho ASCII temporario quando necessario.
        ascii_input, temp_ascii_files = make_ascii_input(input_file, worker_id)

        # Executar chdman createcd — criar diretamente no SSD temporario (F:)
        # Usar arquivo para stderr em vez de pipe (pipe enche com progresso e deadlocka no Windows)
        safe_remove(chd_path)
        err_tmp = CHD_OUTPUT_DIR / f"_chd_err_{worker_id}.txt"
        cmd = [CHDMAN, "createcd", "--input", str(ascii_input), "--output", str(chd_path), "--force"]
        with open(err_tmp, "w") as err_fh:
            proc = subprocess.run(cmd, timeout=1800, creationflags=NO_WINDOW,
                                  stdout=subprocess.DEVNULL, stderr=err_fh)
        if proc.returncode != 0:
            err = ""
            try:
                err = err_tmp.read_text(encoding="utf-8", errors="replace")[:200]
            except:
                pass
            log(f"[W{worker_id}] FAIL {serial}: chdman falhou: {err}")
            safe_remove(chd_path)
            rename_failed_source(filepath, serial, name)
            add_failed_to_importre(serial, name, f"chdman: {err}")
            with _lock:
                _state["failed"] += 1
                _state["errors"].append(f"{serial}: chdman: {err}")
            return "failed"

        # Verificar CHD
        if not chd_path.exists() or chd_path.stat().st_size < 1024:
            log(f"[W{worker_id}] FAIL {serial}: CHD nao criado ou muito pequeno")
            safe_remove(chd_path)
            rename_failed_source(filepath, serial, name)
            add_failed_to_importre(serial, name, "CHD invalido/pequeno")
            with _lock:
                _state["failed"] += 1
                _state["errors"].append(f"{serial}: CHD invalido")
            return "failed"

        # Verify (tambem sem pipe — usar DEVNULL)
        verify = subprocess.run([CHDMAN, "verify", "--input", str(chd_path)],
                                timeout=120, creationflags=NO_WINDOW,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Opcional: copiar CHD do SSD temporario de volta para PSX_DIR
        # (desabilitado por padrao — copia manual ao final e mais rapido)
        # final_path = PSX_DIR / chd_name
        # if chd_path != final_path:
        #     safe_move(chd_path, final_path)
        if verify.returncode != 0:
            log(f"[W{worker_id}] WARN {serial}: CHD verify falhou (mantendo)")
            # Nao deletar — pode ser um warning nao-fatal

        size_mb = chd_path.stat().st_size // 1048576
        log(f"[W{worker_id}] OK {chd_name} ({size_mb}MB)")

        # Registrar arquivos fonte para mover no final do ciclo (consolidacao)
        sources_to_move = []
        if ext != ".cue" and filepath.exists():
            sources_to_move.append(filepath)
        # .cue correspondente a .bin/.ecm
        if ext == ".bin" or ext == ".ecm":
            cue = find_cue_for_bin(filepath if ext == ".bin" else filepath.with_suffix(".bin"))
            if cue and cue.exists():
                sources_to_move.append(cue)
        # .bin do mesmo jogo (multi-track) para .cue
        if ext == ".cue":
            base = filepath.stem
            for sibling in PSX_DIR.glob(f"{base}*.bin"):
                sources_to_move.append(sibling)
        # companheiros de .img (CCD, SUB) e .mdf (MDS)
        if ext == ".img":
            for suffix in (".ccd", ".sub"):
                companion = filepath.with_suffix(suffix)
                if companion.exists():
                    sources_to_move.append(companion)
        elif ext == ".mdf":
            for suffix in (".mds",):
                companion = filepath.with_suffix(suffix)
                if companion.exists():
                    sources_to_move.append(companion)

        with _lock:
            _state["completed"] += 1
            _state.setdefault("sources_to_move", []).extend(str(p) for p in sources_to_move)
        return "completed"

    except subprocess.TimeoutExpired:
        log(f"[W{worker_id}] FAIL {serial}: timeout (30min)")
        safe_remove(chd_path)
        rename_failed_source(filepath, serial, name)
        add_failed_to_importre(serial, name, "timeout 30min")
        with _lock:
            _state["failed"] += 1
            _state["errors"].append(f"{serial}: timeout")
        return "failed"
    except Exception as e:
        log(f"[W{worker_id}] FAIL {serial}: {e}")
        safe_remove(chd_path)
        rename_failed_source(filepath, serial, name)
        add_failed_to_importre(serial, name, f"excecao: {e}")
        with _lock:
            _state["failed"] += 1
            _state["errors"].append(f"{serial}: {e}")
        return "failed"
    finally:
        # Limpar temp
        if temp_bin and temp_bin.exists():
            safe_remove(temp_bin)
        if temp_cue and temp_cue.exists():
            safe_remove(temp_cue)
        if temp_cue_img and temp_cue_img.exists():
            safe_remove(temp_cue_img)
        if temp_mdf_bin and temp_mdf_bin.exists():
            safe_remove(temp_mdf_bin)
        for tf in temp_files:
            safe_remove(tf)
        for tf in temp_ascii_files:
            safe_remove(tf)
        with _lock:
            _state["in_progress"].pop(serial or filepath.stem, None)
        save_state()

def worker(worker_id, queue):
    while True:
        with _lock:
            if not queue:
                break
            item = queue.pop(0)
        try:
            result = convert_one(item, worker_id)
        except Exception as e:
            log(f"[W{worker_id}] ERRO: {e}")
            result = "failed"
        # Se arquivo ainda nao esta pronto, devolver para a fila para tentar depois
        if result == "not_ready":
            with _lock:
                queue.append(item)
            time.sleep(5)
        else:
            time.sleep(0.1)

def _base_key(name):
    """Retorna uma chave base para agrupar arquivos multi-track do mesmo jogo.
    Remove extensao, serial, track, regiao e versao do nome."""
    return _normalize_stem_for_fuzzy(Path(name).stem).lower()


def scan_roms():
    """Escaneia o diretorio PSX e SSD temporario e lista ROMs sem CHD correspondente.
    NAO escaneia DUP_DIR (duplicados) — esses arquivos nao contam na colecao."""
    chd_files = list(PSX_DIR.glob("*.chd")) + list(CHD_OUTPUT_DIR.glob("*.chd"))
    chds = {f.stem.lower() for f in chd_files}
    # Incluir tambem versoes sanitizadas dos stems (para titulos sem serial)
    chds = chds | {sanitize_filename(f.stem).lower() for f in chd_files}
    # Mapa fuzzy de CHDs ja convertidos (stems normalizados)
    chds_norm = {}
    for f in chd_files:
        norm = _normalize_stem_for_fuzzy(f.stem).lower()
        if norm:
            chds_norm.setdefault(norm, f.stem)

    # Pre-detectar arquivos multi-track (Track N) sem CUE mae.
    # Se houver 2+ arquivos com o mesmo _base_key, pular todos os tracks individuais.
    track_pattern = re.compile(r"\(Track \d+\)", re.I)
    track_groups = {}
    search_dirs = [PSX_DIR]  # NAO incluir DUP_DIR
    for pattern in ["*.cue", "*.bin", "*.iso", "*.img", "*.mdf", "*.ecm"]:
        for d in search_dirs:
            for f in d.rglob(pattern):
                if track_pattern.search(f.name):
                    key = _base_key(f.name)
                    track_groups.setdefault(key, []).append(f)
    multi_track_bases = {key for key, files in track_groups.items() if len(files) >= 2}

    items = []
    seen_serials = set()

    # 1. CUEs (multi-track) — prioridade — escanear apenas PSX_DIR
    for d in search_dirs:
        for cue in d.rglob("*.cue"):
            # NAO pular CUEs com "Track" no nome — CUEs sao sempre pontos de entrada validos
            # Pular arquivos ja marcados como nao-conversivel
            if "nao-conversivel" in cue.name.lower():
                continue
            base = cue.stem.lower()
            norm = re.sub(r"\(track \d+\)", "", base, flags=re.I).strip()
            serial = extract_serial(cue.name)
            expected_chd = Path(build_chd_name(serial, cue.stem)).stem.lower()
            # Pular apenas se CHD esperado existe. Heuristica de substring so sem serial,
            # para nao confundir versoes com seriais diferentes (ex: SLPM-86023 vs SLPM-00860).
            if expected_chd in chds or (not serial and any(norm[:20] in c for c in chds)):
                continue
            # Fuzzy match apenas para CUEs com serial — sem serial, nao confiar em fuzzy
            if serial and _normalize_stem_for_fuzzy(cue.stem).lower() in chds_norm:
                continue
            if serial and serial in seen_serials:
                continue
            if serial:
                seen_serials.add(serial)
            items.append({
                "serial": serial,
                "name": re.sub(r"\(Track \d+\)", "", cue.stem, flags=re.I).strip(),
                "file": str(cue),
                "ext": ".cue",
            })

    # 2. BINs sem CUE (single-track) — escanear PSX_DIR
    for d in search_dirs:
        for f in d.rglob("*.bin"):
            if track_pattern.search(f.name) and _base_key(f.name) in multi_track_bases:
                continue
            if "nao-conversivel" in f.name.lower():
                continue
            cue = find_cue_for_bin(f)
            if cue and cue.exists():
                continue  # ja processado via CUE
            base = f.stem.lower()
            norm = re.sub(r"\(track \d+\)", "", base, flags=re.I).strip()
            serial = extract_serial(f.name)
            expected_chd = Path(build_chd_name(serial, f.stem)).stem.lower()
            if expected_chd in chds or (not serial and any(norm[:20] in c for c in chds)):
                continue
            if serial and _normalize_stem_for_fuzzy(f.stem).lower() in chds_norm:
                continue
            if serial and serial in seen_serials:
                continue
            if serial:
                seen_serials.add(serial)
            items.append({
                "serial": serial,
                "name": f.stem,
                "file": str(f),
                "ext": ".bin",
            })

    # 3. ECMs — escanear PSX_DIR
    for d in search_dirs:
        for ecm in d.rglob("*.ecm"):
            if track_pattern.search(ecm.name) and _base_key(ecm.name) in multi_track_bases:
                continue
            if "nao-conversivel" in ecm.name.lower():
                continue
            base = ecm.stem.lower()
            if base in chds:
                continue
            if any(base[:20] in c for c in chds):
                continue
            serial = extract_serial(ecm.name)
            if serial and _normalize_stem_for_fuzzy(ecm.stem).lower() in chds_norm:
                continue
            serial = extract_serial(ecm.name)
            if serial and serial in seen_serials:
                continue
            if serial:
                seen_serials.add(serial)
            items.append({
                "serial": serial,
                "name": ecm.stem,
                "file": str(ecm),
                "ext": ".ecm",
            })

    # 4. ISOs, IMGs, MDFs sem CUE
    for ext_pattern in ["*.iso", "*.img", "*.mdf"]:
        for f in PSX_DIR.rglob(ext_pattern):
            if track_pattern.search(f.name) and _base_key(f.name) in multi_track_bases:
                continue
            if "nao-conversivel" in f.name.lower():
                continue
            cue = find_cue_for_bin(f)
            if cue and cue.exists():
                continue
            base = f.stem.lower()
            serial = extract_serial(f.name)
            expected_chd = Path(build_chd_name(serial, f.stem)).stem.lower()
            if expected_chd in chds or (not serial and any(base[:20] in c for c in chds)):
                continue
            if serial and _normalize_stem_for_fuzzy(f.stem).lower() in chds_norm:
                continue
            if serial and serial in seen_serials:
                continue
            if serial:
                seen_serials.add(serial)
            items.append({
                "serial": serial,
                "name": f.stem,
                "file": str(f),
                "ext": f.suffix.lower(),
            })

    return items

# ============================================================
# DASHBOARD
# ============================================================
def generate_dashboard():
    with _lock:
        s = dict(_state)
    total = s["total"]
    done = s["completed"] + s["failed"] + s["skipped"]
    pct = (done / total * 100) if total > 0 else 0
    in_prog = s["in_progress"]
    errors = s["errors"][-10:]
    log_lines = s["log_lines"][-30:]

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="3">
<style>
body {{ font-family: monospace; background: #1a1a2e; color: #eee; margin: 20px; }}
.stat {{ display: inline-block; background: #16213e; padding: 10px 20px; margin: 5px; border-radius: 8px; }}
.stat .num {{ font-size: 24px; font-weight: bold; }}
.stat .label {{ font-size: 12px; color: #888; }}
.ok {{ color: #4ecca3; }} .fail {{ color: #e94560; }} .skip {{ color: #d29922; }}
.progress {{ background: #16213e; border-radius: 8px; padding: 15px; margin: 10px 0; }}
.bar {{ background: #0f3460; border-radius: 4px; height: 20px; overflow: hidden; }}
.bar-fill {{ background: #4ecca3; height: 100%; transition: width 0.3s; }}
.item {{ background: #16213e; padding: 8px 12px; margin: 4px 0; border-radius: 4px; font-size: 13px; }}
.log {{ background: #0f0f1a; padding: 10px; border-radius: 8px; font-size: 11px; max-height: 300px; overflow-y: auto; }}
.log .ok {{ color: #4ecca3; }} .log .fail {{ color: #e94560; }} .log .skip {{ color: #d29922; }}
h2 {{ color: #4ecca3; }}
</style></head><body>
<h2>CHD Converter v2</h2>
<div>
  <div class="stat"><div class="num">{total}</div><div class="label">Total</div></div>
  <div class="stat"><div class="num ok">{s['completed']}</div><div class="label">OK</div></div>
  <div class="stat"><div class="num fail">{s['failed']}</div><div class="label">Falhas</div></div>
  <div class="stat"><div class="num skip">{s['skipped']}</div><div class="label">Pulados</div></div>
  <div class="stat"><div class="num">{len(in_prog)}</div><div class="label">Em progresso</div></div>
</div>
<div class="progress">
  <div>Progresso: {done}/{total} ({pct:.1f}%)</div>
  <div class="bar"><div class="bar-fill" style="width:{pct}%"></div></div>
</div>
<h3>Convertendo agora ({len(in_prog)})</h3>
{''.join(f'<div class="item">W{v.get("worker",0)}: {k} -> {v.get("chd","")}</div>' for k,v in in_prog.items()) or '<div class="item">Nenhum</div>'}
<h3>Ultimos erros</h3>
{''.join(f'<div class="item fail">{e[:100]}</div>' for e in errors) or '<div class="item">Nenhum</div>'}
<h3>Log</h3>
<div class="log">
{''.join(f'<div class="{ "ok" if "OK" in l else "fail" if "FAIL" in l else "skip" if "SKIP" in l else "" }">{l}</div>' for l in log_lines)}
</div>
</body></html>"""
    return html

COLLECTION_STATUS_PATH = PSX_DIR / "_collection_status.json"

def generate_collection_dashboard():
    """Retorna HTML/JS para a visao unificada da colecao."""
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="30">
<title>Colecao PSX Unificada</title>
<style>
body { font-family: monospace; background: #1a1a2e; color: #eee; margin: 20px; }
h2 { color: #4ecca3; }
.nav { margin-bottom: 20px; }
.nav a { color: #4ecca3; text-decoration: none; margin-right: 20px; }
.stat { display: inline-block; background: #16213e; padding: 10px 20px; margin: 5px; border-radius: 8px; cursor: pointer; }
.stat .num { font-size: 24px; font-weight: bold; }
.stat .label { font-size: 12px; color: #888; }
.converted { color: #4ecca3; } .ready { color: #d29922; } .downloading { color: #4ea3cc; }
.converting { color: #cc4ecc; } .failed { color: #e94560; } .missing { color: #888; }
.filter-bar { margin: 15px 0; }
.filter-bar button { background: #16213e; color: #eee; border: 1px solid #0f3460; padding: 6px 12px; margin: 2px; cursor: pointer; border-radius: 4px; }
.filter-bar button.active { background: #0f3460; }
#search { background: #16213e; color: #eee; border: 1px solid #0f3460; padding: 6px 12px; margin-left: 10px; border-radius: 4px; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; }
th { background: #16213e; padding: 10px; text-align: left; color: #4ecca3; }
td { padding: 8px 10px; border-bottom: 1px solid #16213e; font-size: 13px; }
tr:hover { background: #16213e; }
.status-tag { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; background: #0f3460; }
.path { color: #888; font-size: 11px; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.loading { color: #888; }
</style></head><body>
<h2>Colecao PSX Unificada</h2>
<div class="nav"><a href="/">Dashboard CHD</a> <a href="/collection">Colecao Unificada</a></div>
<div id="stats"></div>
<div class="filter-bar">
  <span>Status:</span>
  <button data-filter="all" class="active">Todos</button>
  <button data-filter="converted">Convertido</button>
  <button data-filter="ready_to_convert">Pronto</button>
  <button data-filter="downloading">Baixando</button>
  <button data-filter="converting">Convertendo</button>
  <button data-filter="queued_to_download">Fila DL</button>
  <button data-filter="download_failed">DL falhou</button>
  <button data-filter="convert_failed">Conv falhou</button>
  <button data-filter="missing">Faltando</button>
  <input type="text" id="search" placeholder="Buscar nome/serial...">
</div>
<div id="content" class="loading">Carregando...</div>
<script>
let allItems = [];
let currentFilter = 'all';

function renderStats(counts) {
  const total = Object.values(counts).reduce((a,b)=>a+b,0);
  const map = {
    converted: ['Convertido', 'converted'],
    ready_to_convert: ['Pronto p/ converter', 'ready'],
    downloading: ['Baixando', 'downloading'],
    converting: ['Convertendo', 'converting'],
    queued_to_download: ['Fila p/ baixar', 'downloading'],
    download_failed: ['DL falhou', 'failed'],
    convert_failed: ['Conv falhou', 'failed'],
    missing: ['Faltando', 'missing']
  };
  let html = `<div class="stat"><div class="num">${total}</div><div class="label">Total</div></div>`;
  for (const [k,[label,cls]] of Object.entries(map)) {
    html += `<div class="stat" data-filter="${k}"><div class="num ${cls}">${counts[k]||0}</div><div class="label">${label}</div></div>`;
  }
  document.getElementById('stats').innerHTML = html;
  document.querySelectorAll('#stats .stat[data-filter]').forEach(el => {
    el.onclick = () => setFilter(el.dataset.filter);
  });
}

function setFilter(f) {
  currentFilter = f;
  document.querySelectorAll('.filter-bar button').forEach(b => b.classList.toggle('active', b.dataset.filter === f));
  renderTable();
}

function renderTable() {
  const q = document.getElementById('search').value.toLowerCase();
  const filtered = allItems.filter(([serial, item]) => {
    if (currentFilter !== 'all' && item.status !== currentFilter) return false;
    const text = (serial + ' ' + (item.name||'') + ' ' + (item.detail||'')).toLowerCase();
    return text.includes(q);
  });
  if (filtered.length === 0) {
    document.getElementById('content').innerHTML = '<p class="loading">Nenhum item encontrado.</p>';
    return;
  }
  let html = `<table><tr><th>Serial</th><th>Nome</th><th>Status</th><th>Detalhe</th><th>Arquivos</th></tr>`;
  for (const [serial, item] of filtered) {
    const cls = {converted:'converted', ready_to_convert:'ready', downloading:'downloading', converting:'converting', queued_to_download:'downloading', download_failed:'failed', convert_failed:'failed', missing:'missing'}[item.status] || '';
    const files = Object.entries(item.files || {}).map(([ext, paths]) => `${ext}:${paths.length}`).join(' ');
    html += `<tr><td>${serial}</td><td>${item.name||'-'}</td><td><span class="status-tag ${cls}">${item.status}</span></td><td>${item.detail||'-'}</td><td class="path">${files}</td></tr>`;
  }
  html += '</table>';
  document.getElementById('content').innerHTML = html;
}

async function load() {
  try {
    const r = await fetch('/api/collection');
    const data = await r.json();
    renderStats(data.status_counts || {});
    allItems = Object.entries(data.collection || {});
    renderTable();
  } catch (e) {
    document.getElementById('content').innerHTML = `<p class="loading">Erro ao carregar: ${e}</p>`;
  }
}

document.querySelectorAll('.filter-bar button').forEach(b => b.onclick = () => setFilter(b.dataset.filter));
document.getElementById('search').oninput = renderTable;
load();
setInterval(load, 30000);
</script>
</body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/status":
            with _lock:
                data = dict(_state)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())
        elif path == "/api/collection":
            try:
                data = json.loads(COLLECTION_STATUS_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {"error": "_collection_status.json nao encontrado ou invalido"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())
        elif path == "/collection":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(generate_collection_dashboard().encode("utf-8"))
        elif path in ("/", "/dashboard"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(generate_dashboard().encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a):
        pass

def start_dashboard(port):
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    log(f"Dashboard: http://127.0.0.1:{port}")
    server.serve_forever()

# ============================================================
# MAIN
# ============================================================
def consolidate():
    """Consolida resultados de um ciclo: move CHDs do SSD temporario para PSX_DIR
    e move arquivos fonte confirmados para D:\\roms\\duplicados. Executado no final de cada ciclo."""
    dup_dir = DUP_DIR if DUP_DIR.exists() else (PSX_DIR / "duplicados")
    dup_dir.mkdir(parents=True, exist_ok=True)

    # Mover CHDs validos do SSD temporario para PSX_DIR
    moved_chds = 0
    for chd in CHD_OUTPUT_DIR.glob("*.chd"):
        if chd.stat().st_size < 1024:
            continue
        dest = PSX_DIR / chd.name
        if dest.exists():
            try:
                dest.unlink()
            except Exception as e:
                log(f"[consolidate] ERRO ao remover CHD destino existente {dest.name}: {e}")
                continue
        try:
            shutil.move(str(chd), str(dest))
            moved_chds += 1
        except Exception as e:
            log(f"[consolidate] ERRO ao mover {chd.name}: {e}")
    if moved_chds:
        log(f"[consolidate] {moved_chds} CHD(s) movido(s) de {CHD_OUTPUT_DIR} para {PSX_DIR}")

    # Mover fontes confirmadas para duplicados/
    with _lock:
        sources = list(_state.get("sources_to_move", []))
        _state["sources_to_move"] = []

    moved_sources = 0
    for src_str in sources:
        src = Path(src_str)
        if not src.exists():
            continue
        try:
            shutil.move(str(src), str(dup_dir / src.name))
            moved_sources += 1
        except Exception as e:
            log(f"[consolidate] ERRO ao mover fonte {src.name}: {e}")
    if moved_sources:
        log(f"[consolidate] {moved_sources} arquivo(s) fonte movido(s) para {dup_dir}")

def run_cycle(args):
    """Executa um ciclo de conversao: escanear, iniciar workers e aguardar."""
    # Escanear ROMs
    log("Escaneando ROMs...")
    items = scan_roms()
    log(f"ROMs sem CHD: {len(items)}")

    if not items:
        return False

    # Resetar estado
    with _lock:
        _state["total"] = len(items)
        _state["completed"] = 0
        _state["failed"] = 0
        _state["skipped"] = 0
        _state["in_progress"] = {}
        _state["queue"] = items
        _state["errors"] = []
        _state["start_time"] = time.time()
        _state["workers"] = args.workers
        # Preservar log_lines anteriores para dashboard continuo
    save_state()

    # Iniciar workers
    log(f"Iniciando {args.workers} workers...")
    threads = []
    for i in range(args.workers):
        t = threading.Thread(target=worker, args=(i, _state["queue"]), daemon=True)
        t.start()
        threads.append(t)

    # Aguardar conclusao
    for t in threads:
        t.join()

    # Resultado do ciclo
    with _lock:
        s = dict(_state)
    elapsed = time.time() - s["start_time"] if s["start_time"] else 0
    log(f"=== CICLO CONCLUIDO ===")
    log(f"OK: {s['completed']} | Falhas: {s['failed']} | Pulados: {s['skipped']} | Tempo: {elapsed:.0f}s")
    save_state()

    # Consolidar: trazer CHDs de volta e mover fontes para duplicados/
    consolidate()
    save_state()
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--port", type=int, default=DASHBOARD_PORT)
    args = parser.parse_args()

    if not acquire_lock():
        log("ERRO: outra instancia do conversor CHD ja esta rodando. Use o dashboard existente.")
        return

    try:
        log("=== CHD Converter v2 ===")
        log(f"chdman: {CHDMAN}")
        log(f"Workers: {args.workers}")

        # Escanear ROMs (dry-run)
        if args.dry_run:
            items = scan_roms()
            log(f"ROMs sem CHD: {len(items)}")
            for item in items[:20]:
                log(f"  {item['serial']:15s} {item['ext']:5s} {Path(item['file']).name}")
            log(f"... e mais {max(0, len(items)-20)} itens")
            return

        # Iniciar dashboard (unico, em thread daemon)
        dash_thread = threading.Thread(target=start_dashboard, args=(args.port,), daemon=True)
        dash_thread.start()

        # Loop continuo: converte, reescaneia, dorme, repete
        while True:
            had_work = run_cycle(args)
            if not had_work:
                log("Nada para converter. Aguardando novos downloads (60s)...")
                time.sleep(60)
            else:
                log("Reescaneando em 10s por novos downloads...")
                time.sleep(10)
    finally:
        release_lock()

if __name__ == "__main__":
    main()
