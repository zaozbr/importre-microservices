#!/usr/bin/env python3
# pylint: disable=broad-except,bare-except,logging-fstring-interpolation,unused-argument,unused-variable,protected-access,subprocess-run-check,unspecified-encoding,f-string-without-interpolation,missing-function-docstring,too-many-statements,too-many-locals,too-many-branches,too-many-arguments,too-many-instance-attributes,too-few-public-methods,too-many-public-methods,import-outside-toplevel,too-many-return-statements,invalid-name,missing-class-docstring,too-many-nested-blocks,consider-using-with,consider-using-f-string,line-too-long,missing-module-docstring,no-else-return,consider-using-dict-comprehension,duplicate-code,too-many-lines,too-many-positional-arguments,superfluous-parens,unnecessary-lambda-assignment,consider-using-generator
"""
importre.py — Sistema automatizado de busca e download de ROMs PSX/PS1

Arquitetura:
  - Servidor HTTP sempre rodando (dashboard + API + controle)
  - Workers como subprocessos independentes (cada um com seu Playwright)
  - Estado compartilhado via queue.json (lock atomico cross-process)
  - Dashboard com AJAX live (poll da API a cada 3s, sem reload)
  - Inteligencia adaptativa (aprende quais sites funcionam melhor)

Uso:
    python importre.py                    # roda tudo (4 workers)
    python importre.py --status           # so gera dashboard e serve
    python importre.py --workers 4 --rounds 4 --limit 4  # teste
    python importre.py --no-headless      # browser visivel
"""

import os
import re
import sys
import json
import time
import shutil
import zipfile
import logging
import argparse
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote_plus, quote
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer


# Cache em memoria de metadata/download URLs do archive.org (evita refetch)
_ARCHIVE_METADATA_CACHE = {}
_ARCHIVE_METADATA_LOCK = threading.Lock()

def archive_request(method, url, **kwargs):
    """Faz request para archive.org direto (sem Tor proxy).
    Tor proxy testado e rejeitado — overhead de Tor (0.02-0.05MB/s) é pior que
    rate limit do archive.org direto. Ver lição 45.
    Cookies de sessão (logged-in-sig/logged-in-user) são enviados automaticamente
    pelo aria2c via --load-cookies. Para requests Python, adicionar manualmente.
    Tenta HTTPS primeiro (CDN mais rápido) e fallback HTTP.
    """
    from requests.adapters import HTTPAdapter
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    # Session sem retries — falha rapido em vez de esperar 30s+ por retry
    s = requests.Session()
    adapter = HTTPAdapter(max_retries=0, pool_connections=20, pool_maxsize=50)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    # SEM Tor proxy — Tor testado e rejeitado (lição 45)
    # Cookies de sessão do archive.org (auth = rate limit maior + coleções restritas)
    try:
        import json as _json
        _cookies_path = Path(r"D:\roms\library\roms\_importre_state\archive_session.json")
        if _cookies_path.exists():
            _cookies = _json.loads(_cookies_path.read_text(encoding="utf-8"))
            s.cookies.update(_cookies)
    except Exception:
        pass
    # URLs para tentar (HTTPS primeiro — CDN mais rápido com cookies)
    urls_to_try = []
    if url.startswith("http://archive.org"):
        urls_to_try = [url.replace("http://archive.org", "https://archive.org", 1), url]
    elif url.startswith("https://archive.org"):
        urls_to_try = [url, url.replace("https://archive.org", "http://archive.org", 1)]
    else:
        urls_to_try = [url]
    last_err = None
    for u in urls_to_try:
        try:
            if method == "get":
                return s.get(u, **kwargs)
            elif method == "post":
                return s.post(u, **kwargs)
            elif method == "head":
                return s.head(u, **kwargs)
            else:
                return s.request(method, u, **kwargs)
        except Exception as e:
            last_err = e
            continue
    raise last_err if last_err else Exception("archive_request falhou")
import urllib.parse

import requests
from bs4 import BeautifulSoup

# === Nova arquitetura: workers escrevem em arquivos individuais; robot cuida da fila ===
sys.path.insert(0, str(Path(__file__).parent))
from _worker_state import (
    set_worker_download, set_worker_search, set_worker_idle,
    post_event, get_all_worker_states,
)
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ============================================================
# CONFIG
# ============================================================

PSX_DIR = Path(r"D:\roms\library\roms\psx")
ROMS_DIR = Path(r"D:\roms\library\roms")
MD_PATH = ROMS_DIR / "PSX_Colecao_Faltantes.md"
STATE_DIR = ROMS_DIR / "_importre_state"
BLACKLIST_PATH = STATE_DIR / "blacklist.json"
SITES_PATH = STATE_DIR / "sites.json"
QUEUE_PATH = STATE_DIR / "queue.json"
DASHBOARD_PATH = STATE_DIR / "dashboard.html"
DOWNLOADS_TMP = STATE_DIR / "downloads"
DOWNLOAD_DIR = DOWNLOADS_TMP
LOG_PATH = STATE_DIR / "importre.log"
CONTROL_PATH = STATE_DIR / "control.json"
LOCK_PATH = STATE_DIR / "queue.lock"
LEARN_PATH = STATE_DIR / "learning.json"
COVERS_DIR = Path(os.path.expanduser("~/Documents/DuckStation/covers"))
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8765

SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"
DEFAULT_WORKERS = 40
TASK_TIMEOUT = 600  # 10 min — task travada eh morta
SCRIPT_PATH = Path(__file__).resolve()

ROM_EXTS = {".bin", ".cue", ".img", ".ccd", ".sub", ".ecm", ".chd", ".mdf", ".mds", ".iso", ".pbp"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".gz", ".bz2", ".tar"}


def get_no_window_kwargs():
    """Retorna kwargs para subprocess.Popen/run sem janela e sem roubar foco no Windows."""
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
        )
    return kwargs


INITIAL_SITES = {
    "blueroms": {
        "url": "https://www.blueroms.ws",
        "search_url": "https://www.blueroms.ws/ps1?search={query}",
        "type": "direct_search",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "romsretro": {
        "url": "https://romsretro.com",
        "search_url": "https://romsretro.com/roms/psx/?search={query}",
        "type": "direct_search",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "cdromance": {
        "url": "https://cdromance.org",
        "search_url": "https://cdromance.org/?s={query}",
        "type": "direct_search",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "vimm": {
        "url": "https://vimm.net",
        "search_url": "https://vimm.net/vault/?p=detail&search={query}",
        "type": "direct_search",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "archive_org": {
        "url": "https://archive.org",
        "search_url": "https://archive.org/advancedsearch.php?q={query}+AND+mediatype%3Asoftware&fl[]=identifier&fl[]=title&fl[]=downloads&rows=20&page=1&output=json",
        "type": "api_search",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
}

STATE_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_TMP.mkdir(parents=True, exist_ok=True)

# ── aria2c download engine ──────────────────────────────────────────
# Motor de download robusto: multi-chunk (16 conexões), resume automático,
# retry infinito, nunca crashea (binário C++ compilado, sem GIL).
_ARIA2_MGR = None
_ARIA2_LOCK = threading.Lock()

def _get_aria2():
    """Singleton Aria2Manager — inicia daemon se necessário."""
    global _ARIA2_MGR
    with _ARIA2_LOCK:
        if _ARIA2_MGR is None:
            try:
                from _aria2_manager import Aria2Manager
                _ARIA2_MGR = Aria2Manager()
            except ImportError:
                log.warning("_aria2_manager não disponível — usando requests fallback")
                return None
        if not _ARIA2_MGR.is_daemon_running():
            if not _ARIA2_MGR.start_daemon():
                log.warning("aria2c daemon não pôde ser iniciado — usando requests fallback")
                return None
        return _ARIA2_MGR

def _requests_download(url, dest_path, serial, expected_size=0, timeout=600):
    """
    Fallback: baixa arquivo via requests (single connection, sem resume).
    Usado quando aria2c daemon está indisponível.
    """
    import requests as _requests
    log.info(f"[fallback] {serial} baixando via requests: {url[:80]}")
    try:
        resp = _requests.get(url, stream=True, timeout=30, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        if total == 0:
            total = expected_size
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        t0 = time.time()
        last_report = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=2 * 1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_report > 2:
                        last_report = now
                        speed = downloaded / (now - t0) if now > t0 else 0
                        if total > 0:
                            queue_update_progress(serial, downloaded, total, int(speed))
        queue_clear_progress(serial)
        actual = dest_path.stat().st_size
        if actual < 1024:
            dest_path.unlink(missing_ok=True)
            return None, f"download muito pequeno ({actual} bytes)"
        elapsed = time.time() - t0
        speed_final = actual / elapsed if elapsed > 0 else 0
        return dest_path, f"baixado via requests: {actual // 1024 // 1024}MB em {elapsed:.1f}s = {int(speed_final // 1024)}KB/s"
    except Exception as e:
        queue_clear_progress(serial)
        dest_path.unlink(missing_ok=True)
        return None, f"erro requests: {e}"


def _aria2_download(url, dest_path, serial, expected_size=0, timeout=600):
    """
    Baixa arquivo via aria2c com multi-chunk (16 conexões) e resume automático.

    Args:
        url: URL do arquivo
        dest_path: Path destino completo
        serial: serial do item (para progress reporting)
        expected_size: tamanho esperado em bytes (0 = desconhecido)
        timeout: tempo máximo em segundos
    Returns:
        (dest_path, message) se sucesso, (None, error_msg) se falha
    """
    mgr = _get_aria2()
    if mgr is None:
        # Fallback: download via requests (single connection, sem resume)
        log.warning(f"[aria2] {serial} daemon indisponível — fallback para requests")
        return _requests_download(url, dest_path, serial, expected_size, timeout)

    dest_dir = str(dest_path.parent)
    filename = dest_path.name

    try:
        gid = mgr.add_uri(url, dest_dir=dest_dir, filename=filename, options={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "header": ["Accept: */*", "Connection: keep-alive"],
        })
    except Exception as e:
        return None, f"aria2 add_uri erro: {str(e)[:150]}"

    log.info(f"[aria2] {serial} GID={gid} iniciando: {filename}")

    # Polling de progresso
    t0 = time.time()
    deadline = t0 + timeout
    last_report = 0

    while time.time() < deadline:
        try:
            info = mgr.get_download_info(gid)
            state = info.get("status", "error")
            completed = info.get("completed_length", 0)
            total = info.get("total_length", 0)
            speed = info.get("download_speed", 0)

            # Se erro de RPC (aria2c morto), sair imediatamente
            if state == "error" and "completed_length" not in info:
                log.warning(f"[aria2] {serial} erro RPC: {info.get('error_message','')}")
                queue_clear_progress(serial)
                return None, f"aria2 RPC erro: {info.get('error_message', 'daemon indisponivel')}"

            # Reportar progresso ao dashboard
            if total > 0:
                queue_update_progress(serial, completed, total, speed)
            elif expected_size > 0:
                queue_update_progress(serial, completed, expected_size, speed)

            # Log a cada 5s ou 10MB
            now = time.time()
            if completed - last_report > 10*1024*1024 or now - t0 > 5:
                last_report = completed
                total_mb = (total or expected_size) / 1e6
                comp_mb = completed / 1e6
                spd_mb = speed / 1e6
                conns = info.get("connections", 0)
                log.info(f"[aria2] {serial} {comp_mb:.1f}/{total_mb:.1f}MB {spd_mb:.1f}MB/s conns={conns}")

            if state == "complete":
                queue_clear_progress(serial)
                actual_size = dest_path.stat().st_size
                elapsed = time.time() - t0
                speed_final = actual_size / elapsed if elapsed > 0 else 0
                if actual_size < 1024:
                    dest_path.unlink(missing_ok=True)
                    return None, f"download muito pequeno ({actual_size} bytes)"
                return dest_path, f"baixado: {filename} ({actual_size//1024//1024}MB em {elapsed:.1f}s = {speed_final//1024}KB/s)"

            elif state == "error" or state == "removed":
                queue_clear_progress(serial)
                err = info.get("error_message", "erro desconhecido")
                # Remover arquivo parcial
                dest_path.unlink(missing_ok=True)
                return None, f"aria2 erro: {err}"

            elif state == "waiting" or state == "paused":
                # Ainda na fila
                pass

        except Exception as e:
            log.warning(f"[aria2] {serial} erro consultando status: {e}")

        time.sleep(2)

    # Timeout
    try:
        mgr.pause(gid)
    except:
        pass
    queue_clear_progress(serial)
    return None, f"aria2 timeout após {timeout}s"


# Configurar logging: arquivo sempre; stdout apenas se estiver disponivel
# (evita OSError [Errno 22] quando rodando detached com stdout fechado)
class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler que nao quebra se stdout/stderr estiver fechado/invalido."""
    def emit(self, record):
        try:
            super().emit(record)
        except OSError:
            pass
    def flush(self):
        try:
            super().flush()
        except OSError:
            pass

log_handlers = [logging.FileHandler(LOG_PATH, encoding="utf-8")]
try:
    if sys.stdout is not None and sys.stdout.fileno() >= 0:
        log_handlers.append(SafeStreamHandler(sys.stdout))
except (OSError, ValueError):
    pass
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers,
)
log = logging.getLogger("importre")

# ============================================================
# FILE LOCK CROSS-PROCESS (atomic create)
# ============================================================

# Lock global para threads (muito mais rapido que file lock)
_THREAD_LOCK = threading.Lock()

# === Lock de sites: cada site so baixa 1 item por vez ===
_BUSY_SITES = {}  # site_key -> lista de seriais baixando
_BUSY_SITES_LOCK = threading.Lock()
# Limite maximo de downloads simultaneos por site
# archive_org aguenta muitos paralelos; sites de browser sao mais limitados
SITE_MAX_PARALLEL = {
    # Downloads simultaneos por site — archive.org aguenta muitos paralelos
    "archive_org": 10,
    "archive_org_jp": 10,
    "coolrom": 8,
    "romulation": 5,
    "retrostic": 5,
    "retroiso": 5,
    "romsretro": 5,
    "romspedia": 5,
    "romsfun": 3,
    "romhustler": 3,
    "romsbase": 3,
    "hexrom": 5,
    "consoleroms": 5,
    "romsgames": 5,
    "retromania": 5,
    "romsdl": 5,
    "emuparadise": 3,
    "romspure": 3,
    "roms2000": 3,
    "classicgames": 3,
    "retrogames_games": 3,
    "retrogames_cc": 3,
    "playretrogames": 3,
    "oldiesnest": 3,
    "psxdatacenter_jp": 5,
    "retrostic_jp": 5,
    "homebrew": 5,
    "google": 3,
    "blueroms": 8,
    "cdromance": 3,
    "vimm": 5,
    "romspack": 3,
    "totalroms": 3,
    "romspure_cc": 3,
    "retrobit": 3,
    "freeroms": 3,
    "classicreload": 3,
    "classicgamezone": 3,
    "romulation_org": 3,
    "playretrogames_online": 3,
    "retrogametalk": 3,
}
SITE_DEFAULT_PARALLEL = 5  # default: max 5 downloads por site

# === Progresso de downloads (compartilhado com servidor/dashboard) ===
_DL_PROGRESS = {}
_DL_PROGRESS_LOCK = threading.Lock()
_DL_PROGRESS_WRITE_LOCK = threading.Lock()
_DL_PROGRESS_LAST_WRITE = 0
DL_PROGRESS_PATH = STATE_DIR / "dl_progress.json"

# === CHD conversion ===
CHDMAN = str(PSX_DIR / "chdman.exe")
INVALID_CHARS = '<>:"/\\|?*'


def make_search_queries(name, serial=None):
    """Gera variações de query para aumentar chance de match.

    Variações: nome limpo, sem região, sem subtítulo, só primeira parte,
    serial sem hífen, nome + serial.
    """
    queries = []
    base = re.sub(r"\(.*?\)", "", name).strip()
    base = re.sub(r"\[.*?\]", "", base).strip()
    base = re.sub(r"\s+", " ", base).strip()
    if base:
        queries.append(base)
        queries.append(re.sub(r"[^\w\s]", "", base).strip())
    # Sem região NTSC/PAL/USA/JP etc
    no_region = re.sub(r"\b(USA|Europe|Japan|NTSC|Pal|Jap|EUR|US|UE|J)\b", "", base, flags=re.IGNORECASE).strip()
    no_region = re.sub(r"\s+", " ", no_region).strip()
    if no_region and no_region.lower() != base.lower():
        queries.append(no_region)
    # Apenas primeira parte do nome (antes de hífen ou dois pontos)
    first_part = re.split(r"[-:]", base)[0].strip()
    if first_part and first_part.lower() != base.lower():
        queries.append(first_part)
    # Serial sem hífen
    if serial:
        serial_plain = serial.replace("-", "").replace("_", "")
        queries.append(serial_plain)
        if base:
            queries.append(base + " " + serial_plain)
    # Remover duplicatas preservando ordem
    seen = set()
    out = []
    for q in queries:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out if out else [name]

# === Pre-search buffer (workers de busca alimentam workers de download) ===
PRESEARCH_BUFFER = {}  # serial -> (result_type, url, site, detail)
PRESEARCH_LOCK = threading.Lock()
PRESEARCH_MAX = 600  # maximo de URLs pre-buscadas no buffer (mais frentes ativas)
_buffer_last_save = 0


def load_presearch_buffer():
    """Carrega buffer do arquivo para memoria (na inicializacao)."""
    global PRESEARCH_BUFFER
    try:
        if BUFFER_PATH.exists():
            data = json.load(open(BUFFER_PATH, encoding="utf-8"))
            with PRESEARCH_LOCK:
                for serial, entry in data.items():
                    if isinstance(entry, dict):
                        t = entry.get("type", "")
                        url = entry.get("url")
                        site = entry.get("site", "")
                        detail = entry.get("detail", "")
                        # Formato antigo corrompido: url pode ser timestamp float
                        if t != "searching" and url and isinstance(url, str):
                            PRESEARCH_BUFFER[serial] = (t, url, site, detail)
                    elif isinstance(entry, (list, tuple)) and len(entry) >= 4:
                        t, url, site, detail = entry[0], entry[1], entry[2], entry[3]
                        if t != "searching" and url and isinstance(url, str):
                            PRESEARCH_BUFFER[serial] = (t, url, site, detail)
            log.info(f"Buffer carregado: {len(PRESEARCH_BUFFER)} itens ready")
    except Exception as e:
        log.debug(f"load_presearch_buffer: {e}")

# === Round-robin de sites ===
# Contador global de rotacao — cada searcher pega a proxima posicao
_SITE_ROTATION_COUNTER = 0
_SITE_ROTATION_LOCK = threading.Lock()

def get_rotated_site_order(all_sites, sites_config):
    """Retorna lista de sites rotacionada (round-robin global).
    Cada chamada pega uma posicao inicial diferente, distribuindo a carga."""
    global _SITE_ROTATION_COUNTER
    with _SITE_ROTATION_LOCK:
        start = _SITE_ROTATION_COUNTER
        _SITE_ROTATION_COUNTER = (_SITE_ROTATION_COUNTER + 1) % max(len(all_sites), 1)
    # Ordenar por prioridade base
    # Homebrew e um site virtual interno — forca prioridade 0 para ser primeiro quando aplicavel
    ordered = sorted(all_sites, key=lambda s: 0 if s == "homebrew" else sites_config.get(s, {}).get("priority", 99))
    # Rotacionar: mover 'start' posicoes para frente
    if start > 0 and len(ordered) > 1:
        ordered = ordered[start:] + ordered[:start]
    return ordered

def save_presearch_buffer():
    """Persiste PRESEARCH_BUFFER em arquivo para o dashboard ler."""
    global _buffer_last_save
    now = time.time()
    if now - _buffer_last_save < 1.0:
        return  # Throttle: max 1x por segundo
    _buffer_last_save = now
    try:
        with PRESEARCH_LOCK:
            data = {}
            for serial, entry in PRESEARCH_BUFFER.items():
                if isinstance(entry, tuple):
                    result_type, url, site, detail = entry
                    data[serial] = {"type": result_type, "url": url, "site": site, "detail": detail}
                else:
                    data[serial] = entry
        save_json(BUFFER_PATH, data)
    except Exception as e:
        log.error(f"save_presearch_buffer erro: {e}")

# === Search misses (seriais ja buscados e nao encontrados) ===
SEARCH_MISSES = set()
SEARCH_MISSES_LOCK = threading.Lock()
MISSES_PATH = STATE_DIR / "search_misses.json"
BUFFER_PATH = STATE_DIR / "search_buffer.json"

def acquire_site(site_key, serial):
    """Tenta reservar um site para download. Retorna True se conseguiu.
    Permite multiplos downloads paralelos do mesmo site (ate SITE_MAX_PARALLEL)."""
    with _BUSY_SITES_LOCK:
        current = _BUSY_SITES.get(site_key, [])
        max_parallel = SITE_MAX_PARALLEL.get(site_key, SITE_DEFAULT_PARALLEL)
        if len(current) >= max_parallel:
            log.debug(f"acquire_site {site_key} full: {len(current)}/{max_parallel}")
            return False  # site no limite
        _BUSY_SITES[site_key] = current + [serial]
        return True


def release_site(site_key, serial=None):
    """Libera um slot do site apos download terminar.
    Se serial fornecido, remove aquele serial especifico (corrige bug de
    remover o ultimo elemento quando ha downloads paralelos do mesmo site)."""
    with _BUSY_SITES_LOCK:
        current = _BUSY_SITES.get(site_key, [])
        if not current:
            _BUSY_SITES.pop(site_key, None)
            return
        if serial and serial in current:
            current.remove(serial)
        elif len(current) <= 1:
            _BUSY_SITES.pop(site_key, None)
            return
        else:
            current = current[:-1]
        if current:
            _BUSY_SITES[site_key] = current
        else:
            _BUSY_SITES.pop(site_key, None)


def get_busy_sites():
    """Retorna dict de sites ocupados (copia)."""
    with _BUSY_SITES_LOCK:
        return {k: v[0] if isinstance(v, list) and v else v for k, v in _BUSY_SITES.items()}


def file_lock(timeout=15):
    """Lock hibrido: threading.Lock para threads + file lock para subprocessos."""
    # Primeiro adquirir thread lock (rapido, intra-processo)
    if not _THREAD_LOCK.acquire(timeout=timeout):
        raise RuntimeError("file_lock: nao foi possivel adquirir thread lock")
    # Depois file lock (para subprocesso do servidor HTTP nao ler arquivo parcial)
    start = time.time()
    while time.time() - start < timeout:
        try:
            fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                with open(LOCK_PATH, "r") as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                except (ProcessLookupError, PermissionError, OSError):
                    os.remove(LOCK_PATH)
                    continue
            except:
                pass
            time.sleep(0.05)
    _THREAD_LOCK.release()
    raise RuntimeError("file_lock: nao foi possivel adquirir file lock")


def file_unlock(acquired):
    if acquired:
        try:
            os.remove(LOCK_PATH)
        except:
            pass
        try:
            _THREAD_LOCK.release()
        except:
            pass


def load_json(path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Normalizar in_progress/failed para dict se forem list (compatibilidade)
            if isinstance(data, dict) and "in_progress" in data:
                ip = data["in_progress"]
                if isinstance(ip, list):
                    data["in_progress"] = {item.get("serial", str(i)): item for i, item in enumerate(ip) if isinstance(item, dict)}
            if isinstance(data, dict) and "failed" in data:
                fl = data["failed"]
                if isinstance(fl, list):
                    data["failed"] = {item.get("serial", str(i)): item for i, item in enumerate(fl) if isinstance(item, dict)}
            return data
        except:
            pass
    return default


def save_json(path, data):
    tmp = str(path) + ".tmp"
    for attempt in range(5):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, str(path))  # atomico
            return
        except (OSError, PermissionError) as e:
            if attempt < 4:
                time.sleep(0.1 * (attempt + 1))  # backoff
            else:
                log.error(f"save_json falhou apos 5 tentativas: {e}")
                try:
                    os.unlink(tmp)
                except Exception:
                    pass


def load_sites():
    sites = load_json(SITES_PATH, None)
    if sites is None:
        sites = INITIAL_SITES.copy()
        save_json(SITES_PATH, sites)
    # RomsBase: backend Myrient encerrou em 31/03/2026 — manter desativado
    if "romsbase" in sites:
        sites["romsbase"]["enabled"] = False
    return sites


def save_sites(sites):
    save_json(SITES_PATH, sites)


def load_blacklist():
    return load_json(BLACKLIST_PATH, {"sites": [], "urls": [], "archive_ids": [], "reasons": {}})


def save_blacklist(bl):
    # Garantir que archive_ids existe
    if "archive_ids" not in bl:
        bl["archive_ids"] = []
    save_json(BLACKLIST_PATH, bl)


def add_to_blacklist(bl, site_key=None, url=None, reason=""):
    if site_key and site_key not in bl.get("sites", []):
        bl.setdefault("sites", []).append(site_key)
        bl.setdefault("reasons", {})[site_key] = reason
    if url:
        # Se parece um identifier do archive.org (sem / nem :), adicionar em archive_ids
        if "/" not in url and ":" not in url and "." not in url:
            if url not in bl.get("archive_ids", []):
                bl.setdefault("archive_ids", []).append(url)
        elif url not in bl.get("urls", []):
            bl.setdefault("urls", []).append(url)
    save_blacklist(bl)
    log.warning(f"BLACKLIST: {site_key or url} — {reason}")


def load_control():
    return load_json(CONTROL_PATH, {"action": "none", "paused": False})


def save_control(action="none", paused=None):
    ctrl = load_control()
    if action:
        ctrl["action"] = action
    if paused is not None:
        ctrl["paused"] = paused
    ctrl["timestamp"] = datetime.now().isoformat()
    save_json(CONTROL_PATH, ctrl)


def check_control():
    ctrl = load_control()
    return ctrl.get("action", "none"), ctrl.get("paused", False)


def clear_control():
    save_control(action="none", paused=False)


def load_learning():
    return load_json(LEARN_PATH, {
        "site_stats": {},
        "query_strategies": {},
        "best_sites": [],
    })


def save_learning(learn):
    save_json(LEARN_PATH, learn)


def record_site_result(site, success, strategy="default", speed=0):
    try:
        learn = load_learning()
        stats = learn["site_stats"].setdefault(site, {
            "attempts": 0, "successes": 0, "failures": 0, "last_success": None,
            "speeds": [], "avg_speed": 0,
        })
        stats["attempts"] += 1
        if success:
            stats["successes"] += 1
            stats["last_success"] = datetime.now().isoformat()
            if speed > 0:
                speeds = stats.get("speeds", [])
                speeds.append(speed)
                stats["speeds"] = speeds[-20:]  # manter ultimas 20
                stats["avg_speed"] = sum(speeds) / len(speeds)
        else:
            stats["failures"] += 1
        strat = learn["query_strategies"].setdefault(site, {})
        s = strat.setdefault(strategy, {"attempts": 0, "successes": 0})
        s["attempts"] += 1
        if success:
            s["successes"] += 1
        # Ordenar por velocidade media (desc) — sites mais rapidos primeiro
        # Sites sem velocidade usam taxa de sucesso como fallback
        site_scores = []
        for s_name, s_data in learn["site_stats"].items():
            if s_data["attempts"] > 0:
                rate = s_data["successes"] / s_data["attempts"]
                avg_speed = s_data.get("avg_speed", 0)
                # Score: velocidade em KB/s * taxa de sucesso
                # Sem velocidade: usa taxa * 100 (prioridade baixa)
                score = avg_speed * rate if avg_speed > 0 else rate * 100
                site_scores.append((s_name, score, avg_speed, rate, s_data["attempts"]))
        site_scores.sort(key=lambda x: (-x[1], -x[4]))
        learn["best_sites"] = [{"site": s, "score": sc, "avg_speed": sp, "rate": r, "attempts": a}
                               for s, sc, sp, r, a in site_scores]
        save_learning(learn)
    except Exception as e:
        log.error(f"Erro ao salvar aprendizado: {e}")


def get_optimized_site_order(sites, blacklist):
    learn = load_learning()
    best = learn.get("best_sites", [])
    ordered = []
    # NAO colocar archive_org primeiro — round-robin distribui a carga
    # Sites por ordem de aprendizado (best_sites) primeiro
    for entry in best:
        s = entry["site"]
        if s in sites and s not in blacklist.get("sites", []) and sites[s].get("enabled") and s not in ordered:
            ordered.append(s)
    # archive_org no fim (ultimo recurso — e o mais sobrecarregado)
    for s in sites:
        if s not in ordered and s not in blacklist.get("sites", []) and sites[s].get("enabled") and s != "archive_org":
            ordered.append(s)
    # archive_org por ultimo
    if "archive_org" in sites and sites["archive_org"].get("enabled") and "archive_org" not in blacklist.get("sites", []):
        ordered.append("archive_org")
    return ordered


def parse_missing_list():
    if not MD_PATH.exists():
        log.error(f"Lista nao encontrada: {MD_PATH}")
        return []
    with open(MD_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    items = []
    current_section = ""
    for line in lines:
        l = line.strip()
        if l.startswith("##"):
            current_section = l
            continue
        if not l.startswith("|") or l.startswith("|---") or l.startswith("| #"):
            continue
        parts = [p.strip() for p in l.split("|")]
        if len(parts) < 4:
            continue
        serial = parts[2].strip()
        name = parts[3].strip()
        if serial.startswith("HBREW") or serial.startswith("HOMEBREW"):
            # Homebrew: serial HBREW-XXX eh apenas referencia nossa, nao real
            # Mantemos no item para referencia interna, mas busca/nome usam o nome do jogo
            items.append({
                "serial": serial, "name": name, "region": "HB",
                "section": current_section, "type": "homebrew",
            })
        elif re.match(r"^[A-Z]{3,5}-\d{4,5}$", serial):
            region = "US" if serial.startswith(("SLUS", "SCUS")) else \
                     "EU" if serial.startswith(("SLES", "SCES", "SCED")) else \
                     "JP" if serial.startswith(("SLPS", "SLPM", "SCPS")) else \
                     "KR" if serial.startswith("SLKA") else "??"
            items.append({
                "serial": serial, "name": name, "region": region,
                "section": current_section, "type": "commercial",
            })
        elif "Homebrew" in current_section and len(parts) >= 6:
            cat = parts[2].strip()
            game_name = parts[3].strip()
            dev = parts[4].strip()
            year = parts[5].strip()
            items.append({
                "serial": f"HOMEBREW-{len(items)+1:04d}",
                "name": game_name, "region": "HB",
                "section": current_section, "type": "homebrew",
                "dev": dev, "year": year,
            })
    return items


def check_in_collection(serial, name=None):
    """Verifica se um serial (ou nome normalizado) ja existe na colecao.
    Faz dedup por serial E por nome (multi-region)."""
    try:
        serial_norm = serial.replace("-", "").lower() if serial else ""
        name_norm = normalize_name(name) if name else ""
        for f in os.listdir(PSX_DIR):
            f_lower = f.lower()
            if not any(f_lower.endswith(ext) for ext in ROM_EXTS):
                continue
            # Match por serial
            if serial_norm and serial_norm in f.replace("-", "").lower():
                return True
            # Match por nome normalizado (multi-region dedup)
            if name_norm and len(name_norm) > 5:
                # Extrair nome do arquivo (sem serial, sem extensao)
                base = re.sub(r"[\-_]?(SLUS|SCUS|SLES|SCES|SLPS|SLPM|SCPS)[\-_]?\d{4,5}", "", Path(f).stem)
                base = re.sub(r"[\-_]?(Disc|Disk)\s*\d+", "", base, flags=re.IGNORECASE)
                base_norm = normalize_name(base)
                if base_norm == name_norm:
                    return True
    except:
        pass
    return False


def cleanup_stale_items(max_age_seconds=600):
    """Devolve itens presos em in_progress de volta para a fila.
    Itens que estao em in_progress ha mais de max_age_seconds sao considerados presos
    (worker morreu ou travou). Tambem remove itens sem _worker ou com _worker morto.
    """
    fl = file_lock()
    try:
        data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}, "completed": {}, "failed": {}, "retry_count": {}})
        in_prog = data.get("in_progress", {})
        if not in_prog:
            return 0
        now = datetime.now()
        returned = 0
        for serial in list(in_prog.keys()):
            item = in_prog[serial]
            # Verificar idade do item
            item_time = item.get("_started_at")
            if item_time:
                try:
                    dt = datetime.fromisoformat(item_time)
                    age = (now - dt).total_seconds()
                    if age > max_age_seconds:
                        log.warning(f"Item preso {serial} ha {int(age)}s — devolvendo para fila")
                        item.pop("_phase", None)
                        item.pop("_current_site", None)
                        item.pop("_detail", None)
                        item.pop("_worker", None)
                        item.pop("_started_at", None)
                        data["queue"].append(item)
                        del in_prog[serial]
                        returned += 1
                except Exception:
                    pass
            else:
                # Sem timestamp — devolver (e provavelmente de uma versao antiga)
                log.warning(f"Item preso {serial} sem timestamp — devolvendo para fila")
                item.pop("_phase", None)
                item.pop("_current_site", None)
                item.pop("_detail", None)
                item.pop("_worker", None)
                data["queue"].append(item)
                del in_prog[serial]
                returned += 1
        if returned > 0:
            save_json(QUEUE_PATH, data)
            log.info(f"Cleanup: {returned} itens devolvidos para fila")
        return returned
    except Exception as e:
        log.error(f"cleanup_stale_items erro: {e}")
        return 0
    finally:
        file_unlock(fl)


def init_queue():
    """Cria queue.json se nao existir. Retorna True se criou."""
    if QUEUE_PATH.exists():
        normalize_queue()
        return False
    fl = file_lock()
    try:
        if QUEUE_PATH.exists():
            return False
        items = parse_missing_list()
        queue = []
        skipped = 0
        for item in items:
            if item["type"] == "commercial":
                if check_in_collection(item["serial"], item.get("name", "")):
                    skipped += 1
                    continue
            queue.append(item)
        data = {
            "queue": queue,
            "in_progress": {},
            "completed": {},
            "failed": {},
            "retry_count": {},
            "total": len(queue) + skipped,
            "skipped": skipped,
        }
        save_json(QUEUE_PATH, data)
        log.info(f"Fila criada: {len(queue)} itens, {skipped} ja na colecao")
        return True
    finally:
        file_unlock(fl)


def normalize_queue_item(q_item, name_lookup=None):
    """Normaliza um item da fila: garante dict e chave estavel.
    Retorna (serial, item_dict) ou (None, None) se invalido.
    """
    if isinstance(q_item, dict):
        serial = str(q_item.get("serial", "")).strip()
        name = q_item.get("name", "")
        serial = make_item_key(serial, name)
        q_item["serial"] = serial
        return serial, q_item
    if isinstance(q_item, str):
        raw = q_item.strip()
        name = ""
        if name_lookup and raw in name_lookup:
            name = name_lookup[raw]
        serial = make_item_key(raw, name)
        item = {"serial": serial, "name": name, "region": "??", "section": "", "type": "commercial"}
        return serial, item
    return None, None


def normalize_queue():
    """Normaliza a fila: garante dicts, chaves estaveis e remove duplicatas/concluidos."""
    fl = file_lock()
    try:
        data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}, "completed": {}, "failed": {}, "retry_count": {}})
        queue = data.get("queue", [])
        changed = False
        completed = data.get("completed", {})
        failed = data.get("failed", {})
        in_progress = data.get("in_progress", {})
        if isinstance(in_progress, list):
            in_progress = {item.get("serial", str(i)): item for i, item in enumerate(in_progress) if isinstance(item, dict)}
        name_lookup = {}
        try:
            for item in parse_missing_list():
                name_lookup[item["serial"]] = item.get("name", "")
        except Exception:
            pass

        new_queue = []
        seen_serials = set()
        seen_names = set()
        for q_item in queue:
            serial, item = normalize_queue_item(q_item, name_lookup)
            if not item:
                changed = True
                continue

            # Pular itens ja completados ou falhos
            if serial in completed or serial in failed:
                changed = True
                continue
            # Itens em in_progress (ex: apos crash/reinicio) devem voltar para a fila, nao sumir
            if serial in in_progress:
                changed = True
                ip_item = in_progress.pop(serial)
                ip_item.pop("_phase", None)
                ip_item.pop("_current_site", None)
                ip_item.pop("_detail", None)
                ip_item.pop("_worker", None)
                ip_item.pop("_started_at", None)
                if serial not in seen_serials:
                    new_queue.append(ip_item)
                    seen_serials.add(serial)
                continue

            # Deduplicar por serial
            if serial in seen_serials:
                changed = True
                continue
            seen_serials.add(serial)

            # Deduplicar por nome normalizado (caso o mesmo jogo apareca sem serial)
            name = item.get("name", "")
            name_norm = normalize_name(name)
            if name_norm and len(name_norm) > 5:
                if name_norm in seen_names:
                    changed = True
                    continue
                seen_names.add(name_norm)

            new_queue.append(item)

        if changed:
            data["queue"] = new_queue
            data["in_progress"] = in_progress
            save_json(QUEUE_PATH, data)
            log.info(f"Queue normalizada: {len(new_queue)} itens (chaves estaveis + dedup)")
        return changed
    finally:
        file_unlock(fl)


def queue_next_item(worker_id):
    """Pega proximo item da fila diretamente de queue.json.
    Marca como in_progress e retorna o item.
    Prioriza itens que ja tem URL no buffer (pre-searched).
    """
    fl = file_lock()
    try:
        data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}, "completed": {}, "failed": {}})
        queue = data.get("queue", [])
        in_progress = data.get("in_progress", {})
        completed = data.get("completed", {})
        failed = data.get("failed", {})

        # Carregar buffer para priorizar itens com URL pronta
        buf = buffer_load()
        buffer_serials = set(buf.keys()) if buf else set()

        # Primeira passada: priorizar itens do buffer
        for i, q_item in enumerate(queue):
            serial, item = normalize_queue_item(q_item, {})
            if not serial:
                continue
            if serial in completed or serial in failed or serial in in_progress:
                continue
            if serial in buffer_serials:
                # Item tem URL pronta no buffer — priorizar!
                item["_phase"] = "starting"
                item["_current_site"] = ""
                item["_detail"] = ""
                item["_worker"] = worker_id
                item["_started_at"] = datetime.now().isoformat()
                item["_needs_search"] = False  # ja tem URL

                in_progress[serial] = item
                data["in_progress"] = in_progress
                data["queue"] = queue[:i] + queue[i+1:]
                save_json(QUEUE_PATH, data)
                return item

        # Segunda passada: pegar primeiro item disponivel
        for i, q_item in enumerate(queue):
            serial, item = normalize_queue_item(q_item, {})
            if not serial:
                continue
            if serial in completed or serial in failed or serial in in_progress:
                continue

            # Pegar este item
            item["_phase"] = "starting"
            item["_current_site"] = ""
            item["_detail"] = ""
            item["_worker"] = worker_id
            item["_started_at"] = datetime.now().isoformat()

            in_progress[serial] = item
            data["in_progress"] = in_progress
            data["queue"] = queue[:i] + queue[i+1:]
            save_json(QUEUE_PATH, data)
            return item

        return None
    finally:
        file_unlock(fl)


# === Cache de capas faltantes (thread-safe) ===
_COVER_QUEUE = []
_COVER_QUEUE_LOCK = threading.Lock()
_COVER_QUEUE_LOADED = False

def _load_cover_queue():
    """Carrega lista de capas faltantes (serial + nome)."""
    global _COVER_QUEUE, _COVER_QUEUE_LOADED
    with _COVER_QUEUE_LOCK:
        if _COVER_QUEUE_LOADED:
            return
        covers_dir = COVERS_DIR
        existing = set()
        if covers_dir.exists():
            existing = set(f.stem.upper() for f in covers_dir.glob('*.jpg'))
        # Coletar seriais da fila completed + disco
        serials = {}
        # Do disco
        for f in PSX_DIR.iterdir():
            if not any(f.name.lower().endswith(ext) for ext in list(ROM_EXTS) + [".chd"]):
                continue
            m = re.search(r'(SLUS|SLES|SCES|SLPS|SLPM|SCPS|SCUS|SLKA|SCED)[-_]?(\d{4,5})', f.name, re.I)
            if m:
                serial = f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
                if serial not in existing and serial not in serials:
                    serials[serial] = f.stem
        # Da fila completed
        data = load_json(QUEUE_PATH, {"completed": {}})
        for serial, info in data.get("completed", {}).items():
            if serial.upper() not in existing and serial.upper() not in serials:
                serials[serial.upper()] = info.get("name", serial)
        _COVER_QUEUE = list(serials.items())
        _COVER_QUEUE_LOADED = True
        log.info(f"Cover queue: {len(_COVER_QUEUE)} capas faltantes")

def dl_cover_next(wlog=None):
    """Baixa a proxima capa faltante. Retorna True se baixou algo, False se acabou."""
    global _COVER_QUEUE
    _load_cover_queue()
    with _COVER_QUEUE_LOCK:
        if not _COVER_QUEUE:
            # Recarregar (novas ROMs podem ter sido baixadas)
            global _COVER_QUEUE_LOADED
            _COVER_QUEUE_LOADED = False
            _load_cover_queue()
            if not _COVER_QUEUE:
                return False
        serial, name = _COVER_QUEUE.pop(0)
    try:
        download_cover(serial, name)
        if wlog:
            wlog.info(f"Cover baixado: {serial}")
        return True
    except Exception as e:
        if wlog:
            wlog.debug(f"Cover falhou: {serial} — {e}")
        return True  # contou como tentativa


def download_cover(serial, name):
    """Baixa cover do jogo para a pasta covers do DuckStation.
    Fontes (em ordem de preferencia):
    1. xlenore/psx-covers (GitHub) — covers 2D por serial, ~92-97% cobertura
    2. xlenore/psx-covers 3D — covers 3D por serial (.png)
    3. psxdatacenter.com — estrutura por prefixo/primeira-letra
    """
    if not COVERS_DIR.exists():
        COVERS_DIR.mkdir(parents=True, exist_ok=True)
    cover_path = COVERS_DIR / f"{serial}.jpg"
    if cover_path.exists() and cover_path.stat().st_size > 5000:
        return  # ja existe
    serial_upper = serial.upper()
    # Fonte 1: xlenore/psx-covers (default 2D .jpg)
    cover_urls = [
        f"https://raw.githubusercontent.com/xlenore/psx-covers/main/covers/default/{serial_upper}.jpg",
    ]
    for url in cover_urls:
        try:
            resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"},
                              allow_redirects=True, stream=True)
            if resp.status_code == 200 and "image" in resp.headers.get("content-type", ""):
                with open(cover_path, "wb") as f:
                    for chunk in resp.iter_content(1024 * 64):
                        f.write(chunk)
                if cover_path.stat().st_size > 5000:
                    log.info(f"Cover baixado: {serial} -> {cover_path.name}")
                    return
                cover_path.unlink(missing_ok=True)
        except Exception:
            pass
    log.debug(f"Cover nao encontrado: {serial}")


def queue_mark_success(serial, filepath, site):
    """Marca item como completado em queue.json."""
    fl = file_lock()
    try:
        data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}, "completed": {}, "failed": {}})
        in_progress = data.get("in_progress", {})
        completed = data.get("completed", {})
        if serial in in_progress:
            in_progress.pop(serial)
        item = in_progress.get(serial, {})
        completed[serial] = {
            "file": str(filepath),
            "site": site,
            "name": item.get("name", ""),
            "completed_at": datetime.now().isoformat(),
        }
        data["in_progress"] = in_progress
        data["completed"] = completed
        save_json(QUEUE_PATH, data)
    finally:
        file_unlock(fl)
    log.info(f"SUCESSO: {serial} via {site}")
    try:
        download_cover(serial, "")
    except Exception:
        pass


def queue_mark_failed(serial, reason):
    """Marca item como falho em queue.json (verifica se nao foi completado por outro worker)."""
    fl = file_lock()
    try:
        data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}, "completed": {}, "failed": {}})
        in_progress = data.get("in_progress", {})
        completed = data.get("completed", {})
        failed = data.get("failed", {})
        if serial in completed:
            return  # ja completado por outro worker
        if serial in in_progress:
            in_progress.pop(serial)
        failed[serial] = {"reason": reason, "failed_at": datetime.now().isoformat()}
        data["in_progress"] = in_progress
        data["failed"] = failed
        save_json(QUEUE_PATH, data)
    finally:
        file_unlock(fl)
    log.warning(f"FALHOU: {serial} — {reason}")


_WORKER_ID_LOCAL = threading.local()


def _current_worker_id():
    """Retorna worker_id da thread atual (setado pelo processo)."""
    return getattr(_WORKER_ID_LOCAL, "id", str(threading.current_thread().ident))


def set_current_worker_id(worker_id):
    _WORKER_ID_LOCAL.id = str(worker_id)


def queue_update_phase(serial, phase, site, detail):
    """Atualiza fase do item em in_progress no queue.json."""
    try:
        fl = file_lock()
        try:
            data = load_json(QUEUE_PATH, {"in_progress": {}})
            in_progress = data.get("in_progress", {})
            if serial in in_progress:
                in_progress[serial]["_phase"] = phase
                in_progress[serial]["_current_site"] = site
                in_progress[serial]["_detail"] = detail
                data["in_progress"] = in_progress
                save_json(QUEUE_PATH, data)
        finally:
            file_unlock(fl)
    except Exception as e:
        log.debug(f"queue_update_phase erro: {e}")


def queue_update_progress(serial, downloaded, total, speed):
    """Atualiza progresso de download em dl_progress.json (escrita atomica)."""
    try:
        progress = {}
        if DL_PROGRESS_PATH.exists():
            try:
                with open(DL_PROGRESS_PATH, "r", encoding="utf-8") as f:
                    progress = json.load(f)
            except (json.JSONDecodeError, ValueError):
                progress = {}
        progress[serial] = {
            "downloaded": downloaded,
            "total": total,
            "speed": speed,
            "ts": time.time(),
        }
        # Escrita atomica: escrever em .tmp e renomear
        tmp = str(DL_PROGRESS_PATH) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(progress, f)
        os.replace(tmp, str(DL_PROGRESS_PATH))
    except Exception as e:
        log.debug(f"queue_update_progress erro: {e}")


def queue_clear_progress(serial):
    """Remove item de dl_progress.json (escrita atomica)."""
    try:
        progress = {}
        if DL_PROGRESS_PATH.exists():
            try:
                with open(DL_PROGRESS_PATH, "r", encoding="utf-8") as f:
                    progress = json.load(f)
            except (json.JSONDecodeError, ValueError):
                progress = {}
        if serial in progress:
            del progress[serial]
            tmp = str(DL_PROGRESS_PATH) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(progress, f)
            os.replace(tmp, str(DL_PROGRESS_PATH))
    except Exception as e:
        log.debug(f"queue_clear_progress erro: {e}")


def get_dl_progress():
    """Retorna progresso lido pelo robot (dl_progress.json)."""
    try:
        if DL_PROGRESS_PATH.exists():
            with open(DL_PROGRESS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def queue_return_item(item):
    """Devolve item para a fila (quando worker nao consegue processar)."""
    serial = item.get("serial", "")
    if not serial:
        return
    fl = file_lock()
    try:
        data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}})
        in_progress = data.get("in_progress", {})
        queue = data.get("queue", [])
        if serial in in_progress:
            ip_item = in_progress.pop(serial)
            ip_item.pop("_phase", None)
            ip_item.pop("_current_site", None)
            ip_item.pop("_detail", None)
            ip_item.pop("_worker", None)
            ip_item.pop("_started_at", None)
            queue.append(ip_item)
            data["in_progress"] = in_progress
            data["queue"] = queue
            save_json(QUEUE_PATH, data)
    finally:
        file_unlock(fl)


def queue_has_pending():
    data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}})
    return len(data.get("queue", [])) > 0 or len(data.get("in_progress", {})) > 0


def normalize_name(name):
    """Normaliza nome do jogo para comparacao (remove regiao, versao, etc)."""
    n = re.sub(r"\(.*?\)", "", name).strip()
    n = re.sub(r"\[.*?\]", "", n).strip()
    n = n.lower()
    n = re.sub(r"[^a-z0-9]", "", n)
    return n


def make_item_key(serial, name):
    """Retorna chave estavel para um item da fila.

    Se houver serial real (SLUS/SLES/etc), usa ele em maiusculas.
    Caso contrario, tenta extrair serial do nome. Se nao houver,
    gera uma chave sintetica NOSERIAL-<hash> a partir do nome
    normalizado, garantindo que itens sem serial tambem possam ser
    processados, deduplicados e marcados como completados.
    """
    text = (str(serial or "") + " " + str(name or "")).strip().upper()
    m = re.search(r"(SLUS|SLES|SCES|SLPS|SLPM|SCPS|SCUS|SLKA|SCED)[-_]?(\d{4,5})", text, re.I)
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    if serial and str(serial).strip():
        s = str(serial).strip().upper()
        if re.match(r"^[A-Z]{3,5}-\d{4,5}$", s):
            return s
        if s.startswith(("NOSERIAL-", "HOMEBREW-")):
            return s
        return s
    n = normalize_name(name or "")
    if not n:
        return "NOSERIAL-EMPTY"
    import hashlib
    h = hashlib.md5(n.encode("utf-8")).hexdigest()[:8]
    return f"NOSERIAL-{h}"


def is_real_serial(serial):
    """Retorna True se serial for um codigo PSX real (SLUS/SLES/SCES/etc)."""
    if not serial or not str(serial).strip():
        return False
    s = str(serial).strip().upper()
    if s.startswith(("NOSERIAL-", "HOMEBREW-")):
        return False
    return bool(re.match(r"^[A-Z]{3,5}-\d{4,5}$", s))


def find_duplicates(directory):
    """Encontra ROMs duplicadas no diretorio. Retorna lista de (manter, remover)."""
    directory = Path(directory)
    roms = []
    for f in directory.iterdir():
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext not in ROM_EXTS and ext not in ARCHIVE_EXTS and ext != ".cue":
            continue
        # Extrair serial do nome
        m = re.search(r"(SLUS|SCUS|SLES|SCES|SLPS|SLPM|SCPS)-\d{4,5}", f.name)
        serial = m.group(0) if m else ""
        # Normalizar nome base (sem serial, sem extensao, sem track)
        base = re.sub(r"\(Track\s+\d+\)", "", f.stem)
        base = re.sub(r"[\-_]?(SLUS|SCUS|SLES|SCES|SLPS|SLPM|SCPS)[\-_]?\d{4,5}", "", base)
        base = re.sub(r"[\-_]?(Disc|Disk)\s*\d+", "", base, flags=re.IGNORECASE)
        base_norm = normalize_name(base)
        # Prioridade: CHD > BIN > ISO > PBP > archives
        priority = {".chd": 1, ".bin": 2, ".iso": 3, ".pbp": 4, ".img": 5,
                   ".zip": 6, ".7z": 7, ".rar": 8, ".cue": 9, ".ecm": 10}
        prio = priority.get(ext, 99)
        roms.append({
            "path": f, "serial": serial, "base": base_norm,
            "ext": ext, "size": f.stat().st_size, "priority": prio,
        })
    # Agrupar por serial (se tiver) ou por nome base
    groups = {}
    for rom in roms:
        key = rom["serial"] if rom["serial"] else rom["base"]
        if len(key) < 3:
            continue
        groups.setdefault(key, []).append(rom)
    # Para cada grupo, ordenar por prioridade e tamanho
    duplicates = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        # Ordenar: CHD primeiro, depois maior tamanho
        group.sort(key=lambda x: (x["priority"], -x["size"]))
        keeper = group[0]
        for dup in group[1:]:
            # Nao remover .cue se o .bin correspondente existe
            if dup["ext"] == ".cue" and any(r["ext"] == ".bin" and r["serial"] == dup["serial"] for r in group):
                continue
            duplicates.append((keeper, dup))
    return duplicates


def cleanup_duplicates(directory, dry_run=False):
    """Remove ROMs duplicadas, mantendo a melhor versao."""
    dups = find_duplicates(directory)
    if not dups:
        log.info("Dedup: nenhuma duplicata encontrada")
        return 0
    removed = 0
    for keeper, dup in dups:
        if dry_run:
            log.info(f"Dedup [dry-run]: remover {dup['path'].name} (manter {keeper['path'].name})")
        else:
            try:
                dup["path"].unlink()
                log.info(f"Dedup: removido {dup['path'].name} (manteve {keeper['path'].name})")
                removed += 1
            except Exception as e:
                log.warning(f"Dedup: erro ao remover {dup['path'].name}: {e}")
    return removed


def queue_get_status():
    """Retorna status completo para dashboard/API."""
    data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}, "completed": {}, "failed": {}, "retry_count": {}, "total": 0, "skipped": 0})
    queue = data.get("queue", [])
    in_prog = data.get("in_progress", {})
    # Garantir que in_prog seja dict (algumas versoes gravam como list)
    if isinstance(in_prog, list):
        in_prog = {item.get("serial", str(i)): item for i, item in enumerate(in_prog) if isinstance(item, dict)}
    completed = data.get("completed", {})
    failed = data.get("failed", {})
    # Aceitar completed/failed como list ou dict
    if isinstance(completed, list):
        completed_count = len(completed)
        completed_items = {}
    else:
        completed_count = len(completed)
        completed_items = dict(list(sorted(completed.items(), key=lambda x: str(x[1].get("timestamp", "")), reverse=True)[:20])) if isinstance(next(iter(completed.values()), None), dict) else {}
    failed_count = len(failed) if isinstance(failed, (list, dict)) else 0
    total = data.get("total", len(queue) + len(in_prog) + completed_count + failed_count)
    skipped = data.get("skipped", 0)
    # Contar itens em busca no buffer (modelo ephemeral: searchers nao usam in_progress)
    buf = buffer_load()
    buf_searching = sum(1 for v in buf.values() if v.get("type") == "searching")
    buf_ready = sum(1 for v in buf.values() if v.get("type") != "searching" and v.get("url"))
    # Construir lista de itens em busca para o dashboard
    searching_items = {}
    for serial, v in buf.items():
        if v.get("type") == "searching":
            # Tentar obter nome da queue
            item_name = ""
            for q in queue:
                if q.get("serial") == serial:
                    item_name = q.get("name", "")
                    break
            searching_items[serial] = {
                "name": item_name,
                "_phase": "searching",
                "_current_site": v.get("site", ""),
                "_detail": v.get("detail", ""),
            }
    return {
        "total": total,
        "skipped": skipped,
        "pending": len(queue),
        "in_progress": len(in_prog) + buf_searching,
        "completed": completed_count,
        "failed": failed_count,
        "searching": sum(1 for v in in_prog.values() if v.get("_phase") == "searching") + buf_searching,
        "starting": sum(1 for v in in_prog.values() if v.get("_phase") == "starting"),
        "downloading": sum(1 for v in in_prog.values() if v.get("_phase") == "downloading"),
        "verifying": sum(1 for v in in_prog.values() if v.get("_phase") == "verifying"),
        "buffer_ready": buf_ready,
        "queue": queue[:20],
        "in_progress_items": {**searching_items, **in_prog},
        "completed_items": completed_items,
        "failed_items": failed,
        "busy_sites": get_busy_sites(),
        "dl_progress": get_dl_progress(),
    }


def verify_download(filepath):
    filepath = Path(filepath)
    if not filepath.exists():
        return False, "arquivo nao existe"
    size = filepath.stat().st_size
    if size < 1024:
        return False, f"muito pequeno ({size} bytes)"
    ext = filepath.suffix.lower()
    if ext in ROM_EXTS and size > 102400:
        return True, "ROM valido"
    if ext in ARCHIVE_EXTS or ext == ".7z":
        try:
            if ext == ".zip":
                with zipfile.ZipFile(filepath, "r") as zf:
                    names = zf.namelist()
                    rom_files = [n for n in names if Path(n).suffix.lower() in ROM_EXTS]
                    if rom_files:
                        return True, f"ZIP com {len(rom_files)} ROM(s)"
                    return False, f"ZIP sem ROMs"
            else:
                result = subprocess.run([SEVEN_ZIP, "l", str(filepath)], capture_output=True, text=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                output = result.stdout + result.stderr
                rom_files = [l for l in output.split("\n") if any(e in l.lower() for e in ROM_EXTS)]
                if rom_files:
                    return True, f"arquivo com ROM"
                return False, "sem ROMs"
        except zipfile.BadZipFile:
            return False, "ZIP corrompido"
        except Exception as e:
            return False, f"erro: {e}"
    if ext == ".pbp" and size > 102400:
        return True, "PBP valido"
    return False, f"extensao nao reconhecida: {ext}"


def extract_rom(filepath, dest_dir, serial=None, name=None):
    """Extrai ROM de arquivo. Se serial/name fornecidos, procura match dentro de archives genericos."""
    filepath = Path(filepath)
    ext = filepath.suffix.lower()
    dest_dir = Path(dest_dir)
    if ext in ROM_EXTS or ext == ".pbp":
        dest = dest_dir / filepath.name
        shutil.move(str(filepath), str(dest))
        return dest
    if ext in ARCHIVE_EXTS or ext == ".7z":
        # Listar conteudo primeiro para procurar match por serial/nome
        serial_lower = (serial or "").lower().replace("-", "")
        name_lower = re.sub(r"\(.*?\)", "", (name or "")).strip().lower()
        name_words = [w for w in re.sub(r"[^a-z0-9\s]", "", name_lower).split() if len(w) > 2]
        try:
            # Listar arquivos dentro do archive
            list_result = subprocess.run([SEVEN_ZIP, "l", str(filepath)], capture_output=True, text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            archive_files = []
            for line in list_result.stdout.split("\n"):
                line_lower = line.lower()
                for rext in ROM_EXTS:
                    if line_lower.endswith(rext):
                        # Extrair nome do arquivo da linha do 7z
                        parts = line.split()
                        if parts:
                            fname = " ".join(parts[5:]) if len(parts) > 5 else parts[-1]
                            archive_files.append((fname, line_lower))
                        break
            # Procurar match por serial primeiro
            best_match = None
            if serial_lower:
                for fname, flow in archive_files:
                    fname_no_dash = flow.replace("-", "").replace("_", "").replace(" ", "")
                    if serial_lower in fname_no_dash:
                        best_match = fname
                        log.info(f"Match por serial {serial}: {fname}")
                        break
            # Procurar match por palavras do nome (rigoroso para evitar jogos errados)
            if not best_match and name_words:
                for fname, flow in archive_files:
                    flow_clean = flow.replace("-", "").replace("_", "")
                    matches = sum(1 for w in name_words if w in flow_clean)
                    # 2-3 palavras: exigir 100%; 4+ palavras: exigir 80%
                    if len(name_words) <= 3:
                        required = len(name_words)
                    else:
                        required = max(3, int(len(name_words) * 0.8))
                    if matches >= required:
                        best_match = fname
                        log.info(f"Match por nome ({matches}/{len(name_words)} palavras, req {required}): {fname}")
                        break
                    else:
                        log.debug(f"Match fraco para {fname}: {matches}/{len(name_words)} palavras (req {required})")
            # Extrair tudo e procurar
            result = subprocess.run([SEVEN_ZIP, "x", str(filepath), f"-o{dest_dir}", "-y"], capture_output=True, text=True, timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode == 0:
                # Se encontramos match, retornar esse arquivo especifico
                if best_match:
                    for root, dirs, files in os.walk(dest_dir):
                        for f in files:
                            if f == best_match or Path(f).name == Path(best_match).name:
                                return Path(root) / f
                # Senao, retornar primeira ROM encontrada
                for f in dest_dir.iterdir():
                    if f.suffix.lower() in ROM_EXTS:
                        return f
                for root, dirs, files in os.walk(dest_dir):
                    for f in files:
                        if Path(f).suffix.lower() in ROM_EXTS:
                            return Path(root) / f
        except Exception as e:
            log.error(f"Erro ao extrair: {e}")
    return None


def sanitize_filename(name):
    """Remove caracteres invalidos de nomes de arquivo."""
    for c in INVALID_CHARS:
        name = name.replace(c, "")
    # Limitar tamanho (Windows: 260 chars para path completo)
    if len(name) > 180:
        name = name[:180]
    return name.strip().rstrip(".")


def build_chd_name(serial, name):
    """Construir nome padrao: Nome-do-jogo-SERIAL.chd"""
    # Limpar nome: remover (Disc X), (Japan), etc entre parenteses
    clean_name = re.sub(r"\s*\(Disc \d+\)\s*", " ", name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\s*\(Japan\)\s*", " ", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\s*\(Europe\)\s*", " ", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\s*\(USA\)\s*", " ", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\s*\(En,Fr,De,Es,It.*?\)\s*", " ", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\s*\(Rev \d+\)\s*", " ", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\s+", " ", clean_name).strip()
    if serial:
        base = f"{clean_name}-{serial}"
    else:
        base = clean_name
    base = sanitize_filename(base)
    return base + ".chd"


def find_cue_for_bin(bin_path):
    """Encontrar arquivo .cue correspondente a um .bin."""
    bin_path = Path(bin_path)
    # Tentar mesmo nome com .cue
    cue = bin_path.with_suffix(".cue")
    if cue.exists():
        return cue
    # Tentar sem (Track XX) no nome
    name_no_track = re.sub(r"\s*\(Track \d+\)\s*", "", bin_path.stem)
    cue = bin_path.parent / (name_no_track + ".cue")
    if cue.exists():
        return cue
    # Tentar CUE generico na mesma pasta
    cues = list(bin_path.parent.glob("*.cue"))
    if len(cues) == 1:
        return cues[0]
    # Procurar CUE que referencia este BIN
    for c in cues:
        try:
            content = c.read_text(encoding="utf-8", errors="replace")
            if bin_path.name in content:
                return c
        except:
            pass
    return None


def convert_to_chd(filepath, serial=None, name=None, dest_dir=None):
    """Converte ROM (bin/cue, iso, img, ccd, mdf, ecm, pbp) para CHD.
    Retorna Path do CHD criado ou None se falhar.
    O arquivo original NAO eh deletado — caller deve deletar apos verificar.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        log.error(f"convert_to_chd: arquivo nao existe: {filepath}")
        return None

    if dest_dir is None:
        dest_dir = filepath.parent
    else:
        dest_dir = Path(dest_dir)

    ext = filepath.suffix.lower()
    chd_name = build_chd_name(serial, name) if serial or name else sanitize_filename(filepath.stem) + ".chd"
    chd_path = dest_dir / chd_name

    # Se CHD ja existe, pular
    if chd_path.exists():
        log.info(f"CHD ja existe: {chd_path.name} — pulando")
        return chd_path

    NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def run_chdman(args, timeout=600):
        """Executa chdman e retorna (ok, output)."""
        cmd = [CHDMAN] + args
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                    creationflags=NO_WINDOW)
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "timeout"
        except Exception as e:
            return False, str(e)

    def verify_chd(chd_file):
        """Verifica integridade do CHD criado."""
        ok, output = run_chdman(["verify", "--input", str(chd_file)], timeout=120)
        return ok

    temp_dir = None

    try:
        if ext == ".chd":
            # Ja eh CHD — apenas renomear se necessario
            if filepath != chd_path:
                shutil.move(str(filepath), str(chd_path))
            return chd_path

        elif ext == ".cue":
            # .cue eh a entrada para createcd
            log.info(f"CHD convert: {filepath.name} -> {chd_path.name}")
            ok, output = run_chdman(["createcd", "--input", str(filepath), "--output", str(chd_path), "--force"], timeout=900)
            if not ok:
                log.error(f"chdman createcd falhou (cue): {output[:200]}")
                if chd_path.exists():
                    chd_path.unlink()
                return None
            if not verify_chd(chd_path):
                log.error(f"CHD verify falhou: {chd_path.name}")
                if chd_path.exists():
                    chd_path.unlink()
                return None
            log.info(f"CHD OK: {chd_path.name} ({chd_path.stat().st_size // 1048576}MB)")
            return chd_path

        elif ext == ".bin":
            # .bin precisa do .cue correspondente
            cue = find_cue_for_bin(filepath)
            if cue:
                log.info(f"CHD convert: {cue.name} -> {chd_path.name}")
                ok, output = run_chdman(["createcd", "--input", str(cue), "--output", str(chd_path), "--force"], timeout=900)
            else:
                # Sem .cue — converter .bin diretamente como raw
                log.info(f"CHD convert (sem cue): {filepath.name} -> {chd_path.name}")
                ok, output = run_chdman(["createcd", "--input", str(filepath), "--output", str(chd_path), "--force"], timeout=900)
            if not ok:
                log.error(f"chdman createcd falhou (bin): {output[:200]}")
                if chd_path.exists():
                    chd_path.unlink()
                return None
            if not verify_chd(chd_path):
                log.error(f"CHD verify falhou: {chd_path.name}")
                if chd_path.exists():
                    chd_path.unlink()
                return None
            log.info(f"CHD OK: {chd_path.name} ({chd_path.stat().st_size // 1048576}MB)")
            return chd_path

        elif ext == ".iso":
            # .iso pode ser convertido diretamente
            log.info(f"CHD convert: {filepath.name} -> {chd_path.name}")
            ok, output = run_chdman(["createcd", "--input", str(filepath), "--output", str(chd_path), "--force"], timeout=900)
            if not ok:
                log.error(f"chdman createcd falhou (iso): {output[:200]}")
                if chd_path.exists():
                    chd_path.unlink()
                return None
            if not verify_chd(chd_path):
                log.error(f"CHD verify falhou: {chd_path.name}")
                return None
            return chd_path

        elif ext == ".img":
            # .img pode ter .ccd (CloneCD) ou .cue
            ccd = filepath.with_suffix(".ccd")
            cue = filepath.with_suffix(".cue")
            if ccd.exists():
                source = ccd
            elif cue.exists():
                source = cue
            else:
                source = filepath
            log.info(f"CHD convert: {source.name} -> {chd_path.name}")
            ok, output = run_chdman(["createcd", "--input", str(source), "--output", str(chd_path), "--force"], timeout=900)
            if not ok:
                log.error(f"chdman falhou (img): {output[:200]}")
                if chd_path.exists():
                    chd_path.unlink()
                return None
            if not verify_chd(chd_path):
                return None
            return chd_path

        elif ext == ".ccd":
            # CloneCD: .ccd eh o indice
            log.info(f"CHD convert: {filepath.name} -> {chd_path.name}")
            ok, output = run_chdman(["createcd", "--input", str(filepath), "--output", str(chd_path), "--force"], timeout=900)
            if not ok:
                log.error(f"chdman falhou (ccd): {output[:200]}")
                if chd_path.exists():
                    chd_path.unlink()
                return None
            if not verify_chd(chd_path):
                return None
            return chd_path

        elif ext == ".mdf":
            # Alcohol 120%: .mdf eh a imagem
            log.info(f"CHD convert: {filepath.name} -> {chd_path.name}")
            ok, output = run_chdman(["createcd", "--input", str(filepath), "--output", str(chd_path), "--force"], timeout=900)
            if not ok:
                log.error(f"chdman falhou (mdf): {output[:200]}")
                if chd_path.exists():
                    chd_path.unlink()
                return None
            if not verify_chd(chd_path):
                return None
            return chd_path

        elif ext == ".ecm":
            # ECM: precisa descomprimir primeiro
            temp_dir = dest_dir / "_ecm_temp"
            temp_dir.mkdir(exist_ok=True)
            bin_out = temp_dir / (filepath.stem + ".bin")
            log.info(f"ECM decode: {filepath.name} -> {bin_out.name}")
            # Usar unecm se disponivel, senao usar 7z
            unecm = PSX_DIR / "unecm.exe"
            if unecm.exists():
                result = subprocess.run([str(unecm), str(filepath), str(bin_out)],
                                        capture_output=True, text=True, timeout=300, creationflags=NO_WINDOW)
                ok = result.returncode == 0
            else:
                # Tentar com 7z (algumas versoes suportam ECM)
                result = subprocess.run([SEVEN_ZIP, "x", str(filepath), f"-o{temp_dir}", "-y"],
                                        capture_output=True, text=True, timeout=300, creationflags=NO_WINDOW)
                ok = result.returncode == 0
            if not ok or not bin_out.exists():
                log.error(f"ECM decode falhou: {filepath.name}")
                return None
            # Agora converter o .bin para CHD
            result = convert_to_chd(bin_out, serial, name, dest_dir)
            # Limpar temp
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
            return result

        elif ext == ".pbp":
            # PBP: precisa extrair com PBP tools (psxtract ou similar)
            # Por enquanto, apenas mover o PBP (ja eh formato PSP/PSX comprimido)
            log.info(f"PBP: movendo {filepath.name} -> {chd_path.name}")
            # PBP nao converte para CHD diretamente — manter como PBP
            pbp_dest = dest_dir / sanitize_filename(filepath.name)
            if filepath != pbp_dest:
                shutil.move(str(filepath), str(pbp_dest))
            return pbp_dest

        else:
            log.warning(f"Formato nao suportado para CHD: {ext}")
            return None

    except Exception as e:
        log.error(f"convert_to_chd erro: {e}")
        if chd_path.exists():
            try:
                chd_path.unlink()
            except:
                pass
        return None
    finally:
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass


def cleanup_rom_originals(chd_path, original_path):
    """Deleta arquivos originais apos conversao CHD bem-sucedida.
    Deleta o arquivo original e seus companions (.cue, .ccd, .sub, .mds, etc).
    """
    chd_path = Path(chd_path)
    original_path = Path(original_path)
    if not chd_path.exists():
        return
    # Deletar arquivo original
    try:
        original_path.unlink()
    except:
        pass
    # Deletar companions do mesmo nome base
    stem = original_path.stem
    parent = original_path.parent
    for ext in [".cue", ".ccd", ".sub", ".mds", ".ecm"]:
        companion = parent / (stem + ext)
        if companion.exists():
            try:
                companion.unlink()
            except:
                pass



def is_romsbase_dead_page(filepath):
    """Detecta se o arquivo baixado do romsbase.com eh a pagina de erro
    do Myrient (backend fechado em 31/03/2026), que vem disfarcada de
    application/octet-stream com Content-Disposition de .zip.
    """
    try:
        fp = Path(filepath)
        if not fp.exists():
            return False
        size = fp.stat().st_size
        if size > 20480:  # pagina de erro tem ~2.3KB; ROMs PSX sao maiores
            return False
        with open(fp, "rb") as f:
            head = f.read(4096)
        if not head.startswith(b"<"):
            return False
        text = head.decode("utf-8", errors="ignore").lower()
        return "myrient" in text and ("shut down" in text or "closure" in text or "march 31" in text)
    except Exception:
        return False


class SiteNavigator:
    def __init__(self, playwright):
        self.pw = playwright
        self.browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--allow-running-insecure-content",
                "--disable-extensions",
                "--disable-popup-blocking",
                "--disable-notifications",
                "--disable-default-apps",
                "--disable-component-extensions-with-background-pages",
                "--disable-background-networking",
                "--disable-sync",
                "--metrics-recording-only",
                "--disable-component-update",
                "--password-store=basic",
                "--use-mock-keychain",
            ]
        )
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True,
            # Preferences de admin: autorizar downloads automaticos sem prompt
            java_script_enabled=True,
            ignore_https_errors=True,
            bypass_csp=True,
        )
        self.page = self.context.new_page()
        # Stealth: disfarcar automacao para passar Cloudflare e similares
        try:
            self.context.add_init_script("""
                // Remover webdriver
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                // Remover chrome runtime
                window.chrome = { runtime: {} };
                // Permissoes falsas
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) =>
                    parameters.name === 'notifications'
                        ? Promise.resolve({ state: Notification.permission })
                        : originalQuery(parameters);
                // Plugins falsos
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                // Languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """)
        except Exception:
            pass
        # Autorizar todos os downloads automaticamente via CDP (admin prefs)
        try:
            cdp = self.context.new_cdp_session(self.page)
            cdp.send("Browser.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": str(DOWNLOAD_DIR),
            })
            cdp.send("Page.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": str(DOWNLOAD_DIR),
            })
        except Exception as e:
            log.debug(f"CDP download behavior: {e}")

    def close(self):
        try:
            self.context.close()
            self.browser.close()
        except:
            pass

    def _safe_goto(self, url, timeout=30000):
        try:
            resp = self.page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            if resp and resp.status >= 400:
                # Cloudflare/403: esperar e tentar de novo (Playwright executa JS)
                if resp.status == 403:
                    time.sleep(5)  # esperar Cloudflare resolver
                    try:
                        self.page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    # Verificar se a pagina carregou apos espera
                    content = self.page.content()[:3000].lower()
                    if "cloudflare" in content or "checking your browser" in content:
                        # Tentar esperar mais (3 rounds de 5s)
                        for _ in range(3):
                            time.sleep(5)
                            try:
                                self.page.wait_for_load_state("networkidle", timeout=8000)
                            except Exception:
                                pass
                            content = self.page.content()[:3000].lower()
                            if "cloudflare" not in content and "checking your browser" not in content:
                                break
                    if "cloudflare" not in content and "checking your browser" not in content:
                        return True, "ok (apos cloudflare)"
                return False, f"HTTP {resp.status}"
            current_url = self.page.url
            # Detecao de bloqueio/captcha/paywall/malware
            # NOTA: "cloudflare" removido da lista — Cloudflare pode ser legitimo
            block_signals = ["captcha", "paywall", "blocked", "access denied",
                           "suspended", "dmca", "removed"]
            if any(x in current_url.lower() for x in block_signals):
                return False, f"bloqueado: {current_url[:80]}"
            # Verificar conteudo da pagina por sinais de paywall/bloqueio
            try:
                content = self.page.content()[:5000].lower()
                paywall_signals = ["please disable your ad blocker", "subscribe to download",
                                 "premium account required", "payment required", "buy premium",
                                 "you have been blocked", "enable javascript and cookies"]
                if any(x in content for x in paywall_signals):
                    return False, "paywall/bloqueio detectado"
                # Detecao de malware/redirecionamento suspeito
                malware_signals = [".exe download", "install our downloader", "install helper",
                                 "your pc is infected", "update your flash", "update your browser"]
                if any(x in content for x in malware_signals):
                    return False, "malware suspeito detectado"
            except Exception:
                pass
            return True, "ok"
        except PWTimeout:
            return False, "timeout"
        except Exception as e:
            return False, str(e)[:200]

    def search_cdromance(self, query, serial, name):
        """Busca no cdromance — navega como humano: busca -> clica no resultado -> acha download.
        Cdromance usa Cloudflare — pode dar 403 na primeira visita, mas Playwright executa JS
        e resolve o desafio. _safe_goto ja trata isso esperando apos 403.
        """
        # Estrategia 1: busca direta no site
        search_url = f"https://cdromance.org/?s={quote_plus(query)}"
        ok, err = self._safe_goto(search_url)
        if not ok:
            # Estrategia 2: tentar pagina inicial primeiro (para resolver Cloudflare)
            ok2, err2 = self._safe_goto("https://cdromance.org/")
            if ok2:
                time.sleep(3)
                ok, err = self._safe_goto(search_url)
            if not ok:
                return None, f"cdromance: {err}"
        # Esperar conteudo carregar (humano espera)
        time.sleep(3)
        try:
            self.page.wait_for_selector("article, .post, .entry, .search-results", timeout=15000)
        except Exception:
            return None, "cdromance: sem resultados (timeout)"

        soup = BeautifulSoup(self.page.content(), "lxml")
        # Procurar links para paginas de jogos (psx-iso no URL)
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if "cdromance.org/psx-iso/" in href or "cdromance.org/psx2psp/" in href:
                links.append((href, text))
        if not links:
            # Fallback: qualquer article com link
            for article in soup.find_all("article"):
                a = article.find("a", href=True)
                if a:
                    links.append((a["href"], a.get_text(strip=True)))

        if not links:
            return None, "cdromance: nenhum link encontrado"

        # Visitar ate 3 resultados
        for link_url, link_text in links[:3]:
            ok, err = self._safe_goto(link_url)
            if not ok:
                continue
            time.sleep(2)  # humano espera pagina carregar
            soup = BeautifulSoup(self.page.content(), "lxml")
            # Procurar link de download direto (.zip, .7z, etc)
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if any(href.endswith(ext) for ext in ARCHIVE_EXTS):
                    return ("direct_url", href), f"cdromance: {link_text}"
            # Procurar botao/link de download
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                href = a["href"]
                if "download" in text and "cdromance" in href:
                    return ("page_url", href), f"cdromance: {link_text}"
            # Procurar form de download
            for form in soup.find_all("form"):
                action = form.get("action", "")
                if "download" in action.lower():
                    return ("page_url", action), f"cdromance: {link_text}"
        return None, "cdromance: sem link de download"

    @staticmethod
    def build_vimm_cache():
        """Reconstroi vimm_cache.json serial->mediaId raspando vimm.net/vault/PS1/{A-Z,0-9}.
        Retorna numero total de entradas no cache.
        """
        import json as _json
        cache_path = STATE_DIR / "vimm_cache.json"
        cache = {}
        if cache_path.exists():
            try:
                cache = _json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                cache = {}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        added = 0
        for letter in letters:
            try:
                url = f"https://vimm.net/vault/PS1/{letter}"
                resp = requests.get(url, timeout=5, headers=headers)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.find_all("a", href=True):
                    m = re.match(r"^/vault/(\d+)$", a["href"])
                    if not m:
                        continue
                    text = a.get_text(strip=True)
                    if not text:
                        continue
                    detail_url = f"https://vimm.net{m.group(0)}"
                    try:
                        resp2 = requests.get(detail_url, timeout=5, headers=headers)
                        if resp2.status_code != 200:
                            continue
                        soup2 = BeautifulSoup(resp2.text, "lxml")
                        page_text = soup2.get_text()
                        serial_match = re.search(r"Serial\s*#?\s*[:\s]*([A-Z]{4}-\d{3,6})", page_text)
                        if not serial_match:
                            continue
                        serial_found = serial_match.group(1)
                        form = soup2.find("form", {"id": "dl_form"})
                        if not form:
                            continue
                        media_id_input = form.find("input", {"name": "mediaId"})
                        if not media_id_input:
                            continue
                        media_id = media_id_input.get("value", "")
                        if not media_id:
                            continue
                        if serial_found not in cache:
                            added += 1
                        cache[serial_found] = media_id
                        time.sleep(0.05)
                    except Exception as e:
                        log.debug(f"build_vimm_cache detail erro: {e}")
                        continue
            except Exception as e:
                log.debug(f"build_vimm_cache letter {letter} erro: {e}")
                continue
        try:
            cache_path.write_text(_json.dumps(cache, indent=2), encoding="utf-8")
        except Exception as e:
            log.debug(f"build_vimm_cache save erro: {e}")
        return len(cache)

    def search_vimm_cache(self, serial, name):
        """Busca no vimm usando cache serial->mediaId (sem Playwright, via requests).
        Estrategia: lista por letra (funciona via requests) -> pagina de detalhe -> extrai serial + mediaId.
        Download direto via archival.cat/PS1/{mediaId}.7z
        """
        import json as _json
        cache_path = STATE_DIR / "vimm_cache.json"
        # Carregar cache
        cache = {}
        if cache_path.exists():
            try:
                cache = _json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Se ja temos o serial no cache, usar
        if serial in cache:
            media_id = cache[serial]
            mirror_url = f"https://archival.cat/PS1/{media_id}.7z"
            return ("direct_url", mirror_url), f"vimm-cache: {serial} -> {media_id}"
        # Se nao tem no cache, raspar lista por letra via requests
        name_clean = re.sub(r"\(.*?\)", "", name).strip()
        first_letter = name_clean[0].upper() if name_clean else "A"
        if first_letter not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            first_letter = "A"
        name_lower = name_clean.lower()
        name_words = [w for w in re.sub(r"[^a-z0-9\s]", "", name_lower).split() if len(w) > 2]
        try:
            # Rasparr lista por letra (funciona via requests!)
            letter_url = f"https://vimm.net/vault/PS1/{first_letter}"
            resp = requests.get(letter_url, timeout=5, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            if resp.status_code != 200:
                return None, f"vimm-cache: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            # Procurar links /vault/NNNN com match por nome
            game_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                m = re.match(r"^/vault/(\d+)$", href)
                if m and text:
                    text_lower = text.lower()
                    score = sum(1 for w in name_words if w in text_lower)
                    if score > 0 or name_lower[:10] in text_lower:
                        game_links.append((href, text, score))
            game_links.sort(key=lambda x: x[2], reverse=True)
            # Visitar pagina de detalhe via requests para pegar serial e mediaId
            for link_url, link_text, _ in game_links[:5]:
                detail_url = f"https://vimm.net{link_url}"
                resp2 = requests.get(detail_url, timeout=5, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                if resp2.status_code != 200:
                    continue
                soup2 = BeautifulSoup(resp2.text, "lxml")
                page_text = soup2.get_text()
                # Validar serial
                serial_match = re.search(r"Serial\s*#?\s*[:\s]*([A-Z]{4}-\d{3,6})", page_text)
                if serial_match:
                    serial_found = serial_match.group(1)
                    if serial.upper() == serial_found.upper():
                        # Encontrou! Pegar mediaId
                        form = soup2.find("form", {"id": "dl_form"})
                        if form:
                            media_id_input = form.find("input", {"name": "mediaId"})
                            if media_id_input:
                                media_id = media_id_input.get("value", "")
                                if media_id:
                                    # Salvar no cache
                                    cache[serial] = media_id
                                    try:
                                        cache_path.write_text(_json.dumps(cache, indent=2), encoding="utf-8")
                                    except Exception:
                                        pass
                                    mirror_url = f"https://archival.cat/PS1/{media_id}.7z"
                                    return ("direct_url", mirror_url), f"vimm: {link_text} (serial:{serial_found})"
        except Exception as e:
            log.debug(f"vimm_cache erro: {e}")
        return None, "vimm-cache: nao encontrado"

    def search_vimm(self, query, serial, name):
        """Busca no vimm.net — navega por letra, acha jogo por nome, entra na pagina, baixa.
        Estrutura real do vimm:
        - Lista por letra: vimm.net/vault/PS1/{letra} — links dos jogos sao /vault/{id}
        - Pagina de detalhe: vimm.net/vault/{id} — tem serial e form de download
        - Form: POST para dl3.vimm.net/ com mediaId
        - Mirror: archival.cat/PS1/{mediaId}.7z
        """
        name_clean = re.sub(r"\(.*?\)", "", name).strip()
        first_letter = name_clean[0].upper() if name_clean else "A"
        if first_letter not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            first_letter = "A"

        name_lower = name_clean.lower()
        name_words = [w for w in re.sub(r"[^a-z0-9\s]", "", name_lower).split() if len(w) > 2]

        # Estrategia 1: pagina por letra
        letter_url = f"https://vimm.net/vault/PS1/{first_letter}"
        ok, err = self._safe_goto(letter_url)
        if not ok:
            return None, f"vimm: {err}"
        time.sleep(2)
        try:
            self.page.wait_for_selector("table a", timeout=15000)
        except Exception:
            return None, "vimm: sem resultados (timeout)"

        soup = BeautifulSoup(self.page.content(), "lxml")
        # Links dos jogos: /vault/{numero} (sem p=, sem system=, sem section=)
        game_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not text:
                continue
            # Padrao: /vault/NNNN (apenas digitos)
            m = re.match(r"^/vault/(\d+)$", href)
            if m:
                text_lower = text.lower()
                score = sum(1 for w in name_words if w in text_lower)
                if score > 0 or name_lower[:10] in text_lower:
                    game_links.append((href, text, score))

        game_links.sort(key=lambda x: x[2], reverse=True)

        if not game_links:
            # Estrategia 2: buscar pela pagina de busca do vimm
            search_url = f"https://vimm.net/vault/?p=search&system=PS1&q={quote_plus(name_clean)}"
            ok, err = self._safe_goto(search_url)
            if ok:
                time.sleep(2)
                soup = BeautifulSoup(self.page.content(), "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True)
                    m = re.match(r"^/vault/(\d+)$", href)
                    if m and text:
                        game_links.append((href, text, 0))

        if not game_links:
            return None, "vimm: jogo nao encontrado"

        # Visitar pagina do jogo e validar serial
        for link_url, link_text, _ in game_links[:3]:
            full_url = f"https://vimm.net{link_url}"
            ok, err = self._safe_goto(full_url)
            if not ok:
                continue
            time.sleep(1)
            soup = BeautifulSoup(self.page.content(), "lxml")
            page_text = soup.get_text()
            # Validar serial na pagina
            serial_found = None
            serial_match = re.search(r"Serial\s*#?\s*[:\s]*([A-Z]{4}-\d{3,6})", page_text)
            if serial_match:
                serial_found = serial_match.group(1)
            if serial and serial_found and serial.upper() != serial_found.upper():
                log_msg(f"vimm: serial mismatch ({serial_found} != {serial}), pulando")
                continue
            # Procurar form de download (dl_form)
            form = soup.find("form", {"id": "dl_form"})
            if form:
                action = form.get("action", "")
                media_id_input = form.find("input", {"name": "mediaId"})
                media_id = media_id_input.get("value") if media_id_input else ""
                if action and media_id:
                    # Usar mirror (download direto .7z) — mais confiavel
                    mirror_url = f"https://archival.cat/PS1/{media_id}.7z"
                    return ("direct_url", mirror_url), f"vimm: {link_text} (serial:{serial_found})"
                if action:
                    return ("page_url", action), f"vimm: {link_text}"
            # Fallback: procurar mirror button
            for btn in soup.find_all("button"):
                mirror = btn.get("data-mirror", "")
                if mirror:
                    onclick = btn.get("onclick", "")
                    # archival.cat/PS1/{mediaId}.7z
                    m = re.search(r"archival\.cat/[^'\"]+\.7z", onclick)
                    if m:
                        return ("direct_url", f"https://{m.group(0)}"), f"vimm: {link_text}"
        return None, "vimm: sem link de download"

    def search_coolrom(self, query, serial, name):
        """Busca no CoolROM via indice local + requests (sem Playwright).
        Estrategia: indice pre-construido por palavra -> match fuzzy -> pagina de detalhe -> link dl.coolrom.com.
        Tem jogos JP e EUR com seriais visiveis na URL.
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

        # Carregar indice CoolROM
        index_path = STATE_DIR / "coolrom_index.json"
        if not index_path.exists():
            return None, "coolrom: indice nao encontrado"
        try:
            idx = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            return None, "coolrom: erro ao carregar indice"
        word_index = idx.get("word_index", {})
        cr_data = idx.get("cr_data", {})

        # Normalizar nome do jogo
        name_clean = re.sub(r"\(.*?\)", "", name).strip()
        name_lower = name_clean.lower()
        name_words = set(w for w in re.sub(r"[^a-z0-9\s]", "", name_lower).split() if len(w) > 2)
        if not name_words:
            return None, "coolrom: nome muito curto"

        # Encontrar candidatos via indice invertido
        candidates = set()
        for w in name_words:
            candidates.update(word_index.get(w, []))
        if not candidates:
            return None, "coolrom: sem candidatos no indice"

        # Score cada candidato
        scored = []
        for ck in candidates:
            entry = cr_data.get(ck)
            if not entry:
                continue
            cr_norm = entry.get("norm", "")
            cr_words = set(w for w in cr_norm.split() if len(w) > 2)
            overlap = len(name_words & cr_words)
            score = overlap / max(len(name_words), 1)
            if score >= 0.5:
                # Bonus por regiao JP
                if entry.get("jp"):
                    score += 0.1
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)

        # Visitar pagina de detalhe dos top 3
        for score, entry in scored[:3]:
            link_url = entry["url"]
            link_text = entry["name"]
            detail_url = f"https://coolrom.com{link_url}"
            try:
                resp2 = requests.get(detail_url, timeout=5, headers=req_headers)
                if resp2.status_code != 200:
                    continue
                # Validar serial na pagina de detalhe para evitar jogos errados
                page_text = resp2.text
                serial_norm = serial.upper().replace("-", "")
                serial_found = serial_norm in page_text.upper().replace("-", "")
                # Series com nomes muito genericos (Simple 1500, SuperLite 1500, etc.)
                # exigem match de serial INDISPENSAVEL, pois o score por nome engana facilmente.
                is_series_generic = any(
                    term in name.lower()
                    for term in ["simple 1500", "superlite 1500", "simple 1500 jitsuyou", "simple characters 2000"]
                )
                if not serial_found:
                    if is_series_generic:
                        log.debug(f"coolrom: serial {serial} nao encontrado na pagina de {link_text} (serie generica) — pulando")
                        continue
                    if score < 0.9:
                        log.debug(f"coolrom: serial {serial} nao encontrado na pagina de {link_text}, pulando")
                        continue
                    log.debug(f"coolrom: serial nao encontrado, mas nome bate muito bem ({score:.0%}) para {link_text}")
                soup2 = BeautifulSoup(page_text, "lxml")
                # Procurar link dl.coolrom.com
                for a in soup2.find_all("a", href=True):
                    href = a["href"]
                    if "dl.coolrom.com" in href:
                        return ("direct_url", href), f"coolrom: {link_text} ({score:.0%})"
            except Exception:
                continue
        return None, "coolrom: nao encontrado"

    def refresh_coolrom_link(self, serial, name):
        """Re-busca na pagina de detalhe do CoolROM para obter um link fresco.
        Usado quando o link cached expirou (HTTP 403/400)."""
        try:
            result = self.search_coolrom(name, serial, name)
            if result and result[0]:
                return result[0][1]  # URL direta
        except Exception as e:
            log.debug(f"refresh_coolrom_link {serial} erro: {e}")
        return None

    def search_retrostic(self, query, serial, name):
        """Busca no Retrostic via cache serial->URL (sem Playwright).
        Cache pre-construido varrendo todas as paginas. Download via POST -> redirect JS.
        Tem jogos JP e EUR com seriais visiveis na URL.
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        # Carregar cache
        cache_path = STATE_DIR / "retrostic_cache.json"
        cache = {}
        if cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Buscar por serial no cache
        if serial and serial in cache:
            link_url = cache[serial]
            return self._retrostic_get_download(link_url, serial, req_headers)
        return None, "retrostic: nao encontrado no cache"

    def _retrostic_get_download(self, link_url, link_text, req_headers):
        """Extrai link de download do Retrostic: GET -> pegar session -> POST -> extrair URL do JS."""
        try:
            detail_url = f"https://www.retrostic.com{link_url}"
            resp1 = requests.get(detail_url, timeout=5, headers=req_headers)
            if resp1.status_code != 200:
                return None, f"retrostic: HTTP {resp1.status_code}"
            soup1 = BeautifulSoup(resp1.text, "lxml")
            # Pegar session do form
            session_val = ""
            rom_url_val = ""
            console_url_val = ""
            for form in soup1.find_all("form"):
                if "download" in form.get("action", "").lower():
                    for inp in form.find_all("input"):
                        name = inp.get("name", "")
                        val = inp.get("value", "")
                        if name == "session":
                            session_val = val
                        elif name == "rom_url":
                            rom_url_val = val
                        elif name == "console_url":
                            console_url_val = val
            if not session_val:
                return None, "retrostic: sem session"
            # POST para download
            post_url = f"https://www.retrostic.com{link_url}/download"
            resp2 = requests.post(post_url, data={
                "rom_url": rom_url_val,
                "console_url": console_url_val,
                "session": session_val,
            }, timeout=15, headers=req_headers)
            if resp2.status_code != 200:
                return None, f"retrostic: POST HTTP {resp2.status_code}"
            # Extrair URL de redirect do JS
            match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', resp2.text)
            if match:
                dl_url = match.group(1)
                if dl_url.startswith("http"):
                    return ("direct_url", dl_url), f"retrostic: {link_text}"
            return None, "retrostic: sem URL de download"
        except Exception as e:
            return None, f"retrostic: erro {e}"

    def search_romsdl(self, query, serial, name):
        """Busca no RomsDL via cache serial->URL (sem Playwright).
        Cache pre-construido varrendo todas as paginas. Download via POST.
        Tem jogos JP e EUR com seriais visiveis na URL.
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        # Carregar cache
        cache_path = STATE_DIR / "romsdl_cache.json"
        cache = {}
        if cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Buscar por serial no cache
        if serial and serial in cache:
            link_url = cache[serial]
            return self._romsdl_get_download(link_url, serial, req_headers)
        return None, "romsdl: nao encontrado no cache"

    def _romsdl_get_download(self, link_url, link_text, req_headers):
        """Extrai link de download do RomsDL: GET -> POST /download -> extrair URL."""
        try:
            detail_url = f"https://romsdl.com{link_url}"
            resp1 = requests.get(detail_url, timeout=5, headers=req_headers)
            if resp1.status_code != 200:
                return None, f"romsdl: HTTP {resp1.status_code}"
            # POST para download
            post_url = f"https://romsdl.com{link_url}/download"
            resp2 = requests.post(post_url, timeout=15, headers=req_headers)
            if resp2.status_code != 200:
                return None, f"romsdl: POST HTTP {resp2.status_code}"
            soup2 = BeautifulSoup(resp2.text, "lxml")
            # Procurar link de download direto
            for a in soup2.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                if ".zip" in href or ".7z" in href or ".iso" in href or ".bin" in href:
                    full_url = href if href.startswith("http") else f"https://romsdl.com{href}"
                    return ("direct_url", full_url), f"romsdl: {link_text}"
            # Procurar redirect JS
            match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', resp2.text)
            if match:
                dl_url = match.group(1)
                if dl_url.startswith("http"):
                    return ("direct_url", dl_url), f"romsdl: {link_text}"
            # Procurar meta refresh
            for meta in soup2.find_all("meta"):
                if meta.get("http-equiv") == "refresh":
                    content = meta.get("content", "")
                    m = re.search(r"url=(.+)", content, re.I)
                    if m:
                        dl_url = m.group(1).strip()
                        full_url = dl_url if dl_url.startswith("http") else f"https://romsdl.com{dl_url}"
                        return ("direct_url", full_url), f"romsdl: {link_text}"
            return None, "romsdl: sem URL de download"
        except Exception as e:
            return None, f"romsdl: erro {e}"

    def search_romspedia(self, query, serial, name):
        """Busca no Romspedia — seriais nos titulos e URLs.
        Busca por serial NAO funciona (retorna pagina generica).
        Busca por NOME funciona via search.php?search_term_string={nome}.
        URL pattern: /roms/playstation-1/{slug}-{serial}
        Download: pagina /download?speed=fast tem contador 6s -> redirect para downloads.romspedia.com
        Tem jogos USA e EUR com seriais visveis. ~5000+ ROMs PS1.
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not serial:
            return None, "romspedia: sem serial"
        try:
            # Busca por NOME (nao por serial — serial nao funciona)
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            # Usar apenas as primeiras 2-3 palavras para busca mais ampla
            name_words = [w for w in short_name.split() if len(w) > 2]
            search_term = " ".join(name_words[:3]) if name_words else short_name
            search_url = f"https://www.romspedia.com/search.php?search_term_string={quote_plus(search_term)}"
            resp = requests.get(search_url, timeout=5, headers=req_headers)
            if resp.status_code != 200:
                return None, f"romspedia: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            # Procurar link que contenha o serial OU o nome
            serial_clean = serial.replace("-", "").lower()
            name_lower = short_name.lower()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                href_lower = href.lower()
                text_lower = text.lower()
                if "/roms/playstation-1/" in href:
                    # Match por serial (mais preciso)
                    if serial.lower() in href_lower or serial_clean in href_lower:
                        game_url = href if href.startswith("http") else f"https://www.romspedia.com{href}"
                        dl_url = game_url.rstrip("/") + "/download?speed=fast"
                        return ("page_url", dl_url), f"romspedia: {serial}"
                    # Match por nome (fallback)
                    if sum(1 for w in name_words if w.lower() in text_lower) >= 2:
                        game_url = href if href.startswith("http") else f"https://www.romspedia.com{href}"
                        dl_url = game_url.rstrip("/") + "/download?speed=fast"
                        return ("page_url", dl_url), f"romspedia: {text[:40]}"
            return None, "romspedia: nao encontrado"
        except Exception as e:
            return None, f"romspedia: erro {e}"

    def search_blueroms(self, query, serial, name):
        """Busca no BlueRoms.ws — PS1 ROMs com download direto via files.blueroms.ws.
        Busca por nome: /ps1?search={nome}. Pagina do jogo: /game/ps1/{slug}.
        Download: pagina /download/{token} contem links diretos para files.blueroms.ws.
        Retorna URL direta do primeiro disco .7z encontrado.
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        if not name:
            return None, "blueroms: sem nome"
        try:
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            search_term = quote_plus(short_name)
            search_url = f"https://www.blueroms.ws/ps1?search={search_term}"
            resp = requests.get(search_url, timeout=5, headers=req_headers)
            if resp.status_code != 200:
                return None, f"blueroms: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            # Procurar link do jogo pelo nome
            name_words = [w.lower() for w in short_name.split() if len(w) > 2]
            best_href = None
            best_text = ""
            best_score = 0
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if not href.startswith("/game/ps1/"):
                    continue
                text_lower = text.lower()
                score = sum(1 for w in name_words if w in text_lower)
                if score > best_score:
                    best_score = score
                    best_href = href
                    best_text = text
            if not best_href:
                return None, "blueroms: jogo nao encontrado"
            game_url = f"https://www.blueroms.ws{best_href}"
            resp2 = requests.get(game_url, timeout=10, headers=req_headers)
            if resp2.status_code != 200:
                return None, f"blueroms: game HTTP {resp2.status_code}"
            soup2 = BeautifulSoup(resp2.text, "lxml")
            # Procurar link de download token
            download_token = None
            for a in soup2.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/download/"):
                    download_token = href
                    break
            if not download_token:
                return None, "blueroms: sem link de download"
            dl_page_url = f"https://www.blueroms.ws{download_token}"
            resp3 = requests.get(dl_page_url, timeout=10, headers=req_headers)
            if resp3.status_code != 200:
                return None, f"blueroms: dl page HTTP {resp3.status_code}"
            soup3 = BeautifulSoup(resp3.text, "lxml")
            # Coletar links diretos .7z/.zip/.iso
            direct_urls = []
            for a in soup3.find_all("a", href=True):
                href = a["href"]
                if ".7z" in href or ".zip" in href or ".iso" in href or ".bin" in href:
                    if href.startswith("http"):
                        direct_urls.append(href)
                    elif href.startswith("/"):
                        direct_urls.append(f"https://www.blueroms.ws{href}")
            if not direct_urls:
                return None, "blueroms: sem URL direta"
            # Preferir arquivo que contenha serial no nome, senao primeiro
            serial_clean = (serial or "").replace("-", "")
            chosen = direct_urls[0]
            for u in direct_urls:
                u_lower = u.lower()
                if serial and serial.lower() in u_lower:
                    chosen = u
                    break
                if serial_clean and serial_clean in u_lower:
                    chosen = u
                    break
            return ("direct_url", chosen), f"blueroms: {best_text[:50]}"
        except Exception as e:
            return None, f"blueroms: erro {e}"

    def search_romsretro(self, query, serial, name):
        """Busca no RomsRetro.com — PSX ROMs com download direto .bin/.zip.
        Busca: /roms/psx/?search={nome}. Pagina do jogo: /roms/psx/{slug}/.
        Download direto: link com .zip ou .bin na pagina.
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        if not name:
            return None, "romsretro: sem nome"
        try:
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            search_term = quote_plus(short_name)
            search_url = f"https://romsretro.com/roms/psx/?search={search_term}"
            resp = requests.get(search_url, timeout=5, headers=req_headers)
            if resp.status_code != 200:
                return None, f"romsretro: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            name_words = [w.lower() for w in short_name.split() if len(w) > 2]
            best_href = None
            best_text = ""
            best_score = 0
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if "/roms/psx/" not in href or href.count("/") < 4:
                    continue
                text_lower = text.lower()
                score = sum(1 for w in name_words if w in text_lower)
                if score > best_score:
                    best_score = score
                    best_href = href
                    best_text = text
            if not best_href:
                return None, "romsretro: jogo nao encontrado"
            game_url = best_href if best_href.startswith("http") else f"https://romsretro.com{best_href}"
            resp2 = requests.get(game_url, timeout=10, headers=req_headers)
            if resp2.status_code != 200:
                return None, f"romsretro: game HTTP {resp2.status_code}"
            soup2 = BeautifulSoup(resp2.text, "lxml")
            for a in soup2.find_all("a", href=True):
                href = a["href"]
                if any(href.lower().endswith(ext) for ext in [".zip", ".bin", ".iso", ".7z"]):
                    dl_url = href if href.startswith("http") else f"https://romsretro.com{href}"
                    return ("direct_url", dl_url), f"romsretro: {best_text[:50]}"
            return None, "romsretro: sem link de download"
        except Exception as e:
            return None, f"romsretro: erro {e}"

    def search_romsgames(self, query, serial, name):
        """Busca no RomsGames — 2534 PSX ROMs com seriais nos titulos.
        Busca WordPress ?s= nao funciona para ROMs. Tentar via Google ou varrer paginas.
        URL pattern: /playstation-rom-{slug}-{serial}/
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not serial:
            return None, "romsgames: sem serial"
        try:
            # Tentar buscar via Google: site:romsgames.net {serial}
            google_url = f"https://www.google.com/search?q=site:romsgames.net+{serial}+playstation-rom&num=5"
            resp = requests.get(google_url, timeout=10, headers=req_headers)
            if resp.status_code == 200:
                # Procurar URLs do romsgames.net no resultado do Google
                for match in re.finditer(r'https?://www\.romsgames\.net/playstation-rom-[^"\'<>\s]+', resp.text):
                    url = match.group(0)
                    if serial.lower() in url.lower():
                        # Visitar a pagina para pegar link de download
                        resp2 = requests.get(url, timeout=5, headers=req_headers)
                        if resp2.status_code == 200:
                            soup2 = BeautifulSoup(resp2.text, "lxml")
                            for a2 in soup2.find_all("a", href=True):
                                href2 = a2["href"]
                                if "download" in href2.lower():
                                    dl_url = href2 if href2.startswith("http") else f"https://www.romsgames.net{href2}"
                                    return ("direct_url", dl_url), f"romsgames: {serial}"
            return None, "romsgames: nao encontrado"
        except Exception as e:
            return None, f"romsgames: erro {e}"

    def search_retromania(self, query, serial, name):
        """Busca no RetroMania — seriais nas URLs.
        Busca por serial NAO filtra (retorna sempre populares).
        Busca por NOME funciona via /roms/playstation?q={nome}.
        URL pattern: /roms/playstation/{slug}-{serial}-{id}
        Tem jogos USA, EUR e JP com seriais nas URLs.
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not serial:
            return None, "retromania: sem serial"
        try:
            # Buscar por nome (serial nao filtra)
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            name_words = [w for w in short_name.lower().split() if len(w) > 2]
            search_url = f"https://retromania.gg/roms/playstation?q={quote_plus(short_name)}"
            resp = requests.get(search_url, timeout=5, headers=req_headers)
            if resp.status_code != 200:
                return None, f"retromania: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            # Procurar por link que contenha o serial
            serial_lower = serial.lower()
            serial_clean = serial.replace("-", "").lower()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                href_lower = href.lower()
                if "/roms/playstation/" in href:
                    # Match por serial na URL (mais preciso)
                    if serial_lower in href_lower or serial_clean in href_lower:
                        game_url = href if href.startswith("http") else f"https://retromania.gg{href}"
                        # Visitar pagina para pegar link de download
                        resp2 = requests.get(game_url, timeout=10, headers=req_headers)
                        if resp2.status_code == 200:
                            soup2 = BeautifulSoup(resp2.text, "lxml")
                            for a2 in soup2.find_all("a", href=True):
                                href2 = a2["href"]
                                if "download" in href2.lower() and ".7z" not in href2 and ".zip" not in href2:
                                    continue  # pular botoes genericos
                                if ".7z" in href2 or ".zip" in href2 or ".bin" in href2 or ("download" in href2.lower() and "/roms/" in href2):
                                    dl_url = href2 if href2.startswith("http") else f"https://retromania.gg{href2}"
                                    return ("direct_url", dl_url), f"retromania: {serial}"
                        return None, "retromania: pagina sem link de download"
            return None, "retromania: nao encontrado"
        except Exception as e:
            return None, f"retromania: erro {e}"

    def search_romsfun(self, query, serial, name):
        """Busca no RomsFun — 5238 PSX ROMs com regiao JP e Fan Translations.
        URL pattern: /roms/playstation/{slug}.html
        Download: /download/{slug}-{id} (com token, espera 60s)
        Tem jogos JP com fan translations!
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not serial:
            return None, "romsfun: sem serial"
        try:
            # Buscar por nome (nao tem busca por serial direto)
            # Tentar buscar pelo nome limpo
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            search_url = f"https://romsfun.com/?s={requests.utils.quote(short_name)}"
            resp = requests.get(search_url, timeout=5, headers=req_headers)
            if resp.status_code != 200:
                return None, f"romsfun: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                # Verificar se o nome bate (pelo menos 2 palavras)
                name_lower = short_name.lower()
                words_match = sum(1 for w in name_lower.split() if w in text)
                if words_match >= 2 and "/roms/playstation/" in href:
                    # Achou! Visitar pagina para pegar link de download
                    game_url = href if href.startswith("http") else f"https://romsfun.com{href}"
                    resp2 = requests.get(game_url, timeout=10, headers=req_headers)
                    if resp2.status_code == 200:
                        soup2 = BeautifulSoup(resp2.text, "lxml")
                        for a2 in soup2.find_all("a", href=True):
                            href2 = a2["href"]
                            if "/download/" in href2:
                                dl_url = href2 if href2.startswith("http") else f"https://romsfun.com{href2}"
                                # Passar a pagina /1 que contem o link real de download
                                return ("direct_url", dl_url + "/1"), f"romsfun: {short_name}"
                    return None, "romsfun: pagina sem link de download"
            return None, "romsfun: nao encontrado"
        except Exception as e:
            return None, f"romsfun: erro {e}"

    def search_retroiso(self, query, serial, name):
        """Busca no RetroISO — ~100 ROMs PS1 com download direto via Google Drive.
        Cache pre-construido por nome. URL pattern: /{slug}-ps1/
        Download: /download/{id} -> redirect para Google Drive (download direto).
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not serial:
            return None, "retroiso: sem serial"
        try:
            # Carregar cache
            cache_path = STATE_DIR / "retroiso_cache.json"
            cache = {}
            if cache_path.exists():
                try:
                    cache = json.loads(cache_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            # Buscar por nome no cache (match fuzzy)
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            name_lower = short_name.lower()
            name_words = [w for w in re.sub(r"[^a-z0-9\s]", "", name_lower).split() if len(w) > 2]
            best_match = None
            best_score = 0
            for cached_name, cached_url in cache.items():
                cached_lower = cached_name.lower()
                score = sum(1 for w in name_words if w in cached_lower)
                if score > best_score:
                    best_score = score
                    best_match = (cached_name, cached_url)
            if best_match and best_score >= 2:
                # Encontrou no cache — visitar pagina para pegar link de download
                cached_name, game_url = best_match
                resp = requests.get(game_url, timeout=10, headers=req_headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        text = a.get_text(strip=True).lower()
                        if "download" in text and "retroiso.com/download/" in href:
                            # Link de download — retorna como direct_url (redirect para Google Drive)
                            return ("direct_url", href), f"retroiso: {cached_name[:40]}"
                return None, "retroiso: pagina sem link de download"
            return None, "retroiso: nao encontrado no cache"
        except Exception as e:
            return None, f"retroiso: erro {e}"

    def search_romhustler(self, query, serial, name):
        """Busca no Rom Hustler — tem filtro de regiao Japan.
        URL pattern: /rom/psx/{slug}
        Tem FTP em ftp.romhustler.net/roms/psx
        Matching relaxado: exige 80% das palavras significativas (ou 2/3 se 1-2 palavras).
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not serial:
            return None, "romhustler: sem serial"
        try:
            # Buscar por nome
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            is_jp = serial.upper().startswith(("SLPS", "SLPM", "SCPS", "SLKA"))
            region_param = "&region=J" if is_jp else ""
            search_url = f"https://romhustler.org/roms/psx?search={requests.utils.quote(short_name)}{region_param}"
            resp = requests.get(search_url, timeout=5, headers=req_headers)
            if resp.status_code != 200:
                return None, f"romhustler: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            name_lower = short_name.lower()
            name_words = [w for w in name_lower.split() if len(w) > 2]  # ignorar palavras curtas
            total_words = len(name_words)
            if total_words == 0:
                return None, "romhustler: nome sem palavras significativas"
            if total_words <= 2:
                required = max(1, int(total_words * 2 / 3))
            else:
                required = max(1, int(total_words * 0.8))
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                # Matching relaxado: pelo menos 80% (ou 2/3 se 1-2 palavras) das palavras significativas
                score = sum(1 for w in name_words if w in text)
                if score >= required and "/rom/psx/" in href:
                    game_url = href if href.startswith("http") else f"https://romhustler.org{href}"
                    resp2 = requests.get(game_url, timeout=10, headers=req_headers)
                    if resp2.status_code == 200:
                        soup2 = BeautifulSoup(resp2.text, "lxml")
                        for a2 in soup2.find_all("a", href=True):
                            href2 = a2["href"]
                            if "download" in href2.lower():
                                dl_url = href2 if href2.startswith("http") else f"https://romhustler.org{href2}"
                                return ("direct_url", dl_url), f"romhustler: {short_name}"
                    return None, "romhustler: pagina sem link de download"
            return None, "romhustler: nao encontrado"
        except Exception as e:
            return None, f"romhustler: erro {e}"

    def search_psxdatacenter_jp(self, query, serial, name):
        """Busca no PSXDataCenter por serial para obter titulo japones.
        Depois usa o titulo JP para buscar no archive.org (muitos ROMs JP estao
        arquivados com titulo em japones, nao com serial).
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        if not serial:
            return None, "psxdc: sem serial"

        # So tentar para seriais japoneses
        if not serial.startswith(("SLPS", "SLPM", "SCPS", "SLKA")):
            return None, "psxdc: nao-JP"

        try:
            # PSXDataCenter URL pattern: /games/J/{first_letter_of_title}/{first_letter}/{SERIAL}.html
            # Mas nao sabemos a primeira letra do titulo. Tentar buscar pelo site.
            # Estrategia: usar a busca do site via Google
            google_query = f"site:psxdatacenter.com {serial}"
            google_url = f"https://www.google.com/search?q={quote_plus(google_query)}&num=5"
            resp = requests.get(google_url, timeout=10, headers=req_headers)
            if resp.status_code != 200:
                return None, f"psxdc: google HTTP {resp.status_code}"

            # Extrair URL do psxdatacenter do resultado do Google
            psxdc_url = None
            for match in re.finditer(r'https?://(?:www\.)?psxdatacenter\.com/games/J/[^"\'<>\s]+\.html', resp.text):
                psxdc_url = match.group(0)
                break

            if not psxdc_url:
                # Tentar URL direta com padrao conhecido
                # SLPS-02000 -> /games/J/F/SLPS-02000.html (F = Final Fantasy)
                # Precisamos tentar varias letras
                for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
                    test_url = f"https://psxdatacenter.com/games/J/{letter}/{serial}.html"
                    try:
                        resp2 = requests.get(test_url, timeout=10, headers=req_headers, allow_redirects=False)
                        if resp2.status_code == 200:
                            psxdc_url = test_url
                            break
                    except:
                        continue

            if not psxdc_url:
                return None, "psxdc: pagina nao encontrada"

            # Visitar a pagina do PSXDataCenter
            resp3 = requests.get(psxdc_url, timeout=10, headers=req_headers)
            if resp3.status_code != 200:
                return None, f"psxdc: HTTP {resp3.status_code}"

            soup = BeautifulSoup(resp3.text, "lxml")
            # Extrair titulo oficial (japones)
            official_title = None
            for tr in soup.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 2 and "Official Title" in tds[0].get_text():
                    official_title = tds[1].get_text(strip=True)
                    break

            if not official_title:
                return None, "psxdc: titulo nao encontrado"

            # Agora buscar no archive.org com o titulo japones
            # Muitos ROMs JP no archive.org usam o titulo em japones
            jp_query = f'"{official_title}" playstation'
            search_url = (
                f"https://archive.org/advancedsearch.php?q={quote_plus(jp_query)}"
                f"+AND+mediatype%3Asoftware&fl[]=identifier&fl[]=title&fl[]=downloads"
                f"&rows=20&page=1&output=json"
            )
            resp4 = archive_request("get", search_url, timeout=(30, 180), headers={"User-Agent": "Mozilla/5.0"})
            if resp4.status_code != 200:
                return None, f"psxdc: archive HTTP {resp4.status_code}"

            docs = resp4.json().get("response", {}).get("docs", [])
            bl = load_blacklist()
            blacklisted_ids = set(bl.get("archive_ids", []))
            blacklist_terms = ["cover", "manual", "art", "scans", "booklet", "insert"]

            for doc in docs:
                if doc["identifier"] in blacklisted_ids:
                    continue
                title = doc.get("title", "").lower()
                if any(term in title for term in blacklist_terms):
                    continue
                # Score: quantas palavras do titulo JP estao no titulo do archive
                jp_words = [w for w in official_title.lower().split() if len(w) > 1]
                score = sum(1 for w in jp_words if w in title)
                if score >= max(1, len(jp_words) // 3):
                    log.info(f"psxdc JP hit: {serial} -> '{official_title}' -> {doc['identifier']}")
                    return ("archive_item", doc["identifier"]), f"psxdc->archive: {official_title[:30]}"

            return None, f"psxdc: titulo '{official_title[:20]}' nao achado no archive"
        except Exception as e:
            return None, f"psxdc: erro {e}"

    def search_retrostic_jp(self, query, serial, name):
        """Busca na secao JP do Retrostic por serial.
        Retrostic tem lista de ROMs JP com serial entre colchetes [SLPS-XXXXX].
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        if not serial:
            return None, "retrostic_jp: sem serial"
        if not serial.startswith(("SLPS", "SLPM", "SCPS", "SLKA")):
            return None, "retrostic_jp: nao-JP"

        try:
            # Retrostic JP: listar todas as ROMs JP e procurar pelo serial
            # A lista e paginada. Buscar nas primeiras paginas.
            for page in range(1, 6):  # tentar 5 paginas
                url = f"https://www.retrostic.com/jp/roms/ps-1?sorting=c&page={page}"
                resp = requests.get(url, timeout=5, headers=req_headers)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                # Procurar por links que contenham o serial
                for a in soup.find_all("a", href=True):
                    text = a.get_text(strip=True)
                    if serial in text or serial.lower().replace("-", "") in text.lower().replace("-", "").replace("_", ""):
                        href = a["href"]
                        if "/roms/" in href or "/ps-1/" in href:
                            # Visitar a pagina do ROM
                            rom_url = href if href.startswith("http") else f"https://www.retrostic.com{href}"
                            resp2 = requests.get(rom_url, timeout=10, headers=req_headers)
                            if resp2.status_code != 200:
                                continue
                            soup2 = BeautifulSoup(resp2.text, "lxml")
                            # Procurar link de download
                            for a2 in soup2.find_all("a", href=True):
                                if "download" in a2["href"].lower() or "download" in a2.get_text(strip=True).lower():
                                    dl_url = a2["href"]
                                    if dl_url.startswith("/"):
                                        dl_url = f"https://www.retrostic.com{dl_url}"
                                    return ("direct_url", dl_url), f"retrostic_jp: {serial}"
                            return None, f"retrostic_jp: pagina encontrada mas sem download {serial}"
                # Se o serial nao esta nesta pagina, continuar
            return None, "retrostic_jp: nao encontrado nas paginas"
        except Exception as e:
            return None, f"retrostic_jp: erro {e}"

    def search_archive_org_jp(self, query, serial, name):
        """Busca no archive.org com estrategias especificas para ROMs japoneses.
        Usa titulo em romaji + termos JP + busca por serial sem hifen.
        """
        req_headers = {"User-Agent": "Mozilla/5.0"}
        if not serial:
            return None, "archive_jp: sem serial"
        if not serial.startswith(("SLPS", "SLPM", "SCPS", "SLKA")):
            return None, "archive_jp: nao-JP"

        bl = load_blacklist()
        blacklisted_ids = set(bl.get("archive_ids", []))
        blacklist_terms = ["cover", "manual", "art", "scans", "booklet", "insert"]

        # Colecoes do archive.org que exigem login (access-restricted-item=true).
        # Download direto retorna HTTP 401 — pular essas colecoes.
        ARCHIVE_RESTRICTED_COLLECTIONS = {
            "PS1_JP_Arquivista",
            "PS1_JP_CHD_Arquivista",
            "chd_psx_jap",
            "chd_psx_jap_p2",
        }

        def search_a(query_str, rows=30):
            search_url = (
                f"https://archive.org/advancedsearch.php?q={quote_plus(query_str)}"
                f"+AND+mediatype%3Asoftware&fl[]=identifier&fl[]=title&fl[]=downloads"
                f"&rows={rows}&page=1&output=json"
            )
            resp = archive_request("get", search_url, timeout=(30, 180), headers=req_headers)
            if resp.status_code != 200:
                return []
            return resp.json().get("response", {}).get("docs", [])

        def normalize_for_match(name):
            n = re.sub(r"\(.*?\)", "", name)
            n = re.sub(r"\[.*?\]", "", n)
            n = re.sub(r"[^\w\s]", " ", n)
            n = re.sub(r"\s+", " ", n).strip().lower()
            return n

        # Estrategia 0: indice JP publico pre-construido (lookup local, instantaneo)
        # Substitui archive_jp_name_index.json (restrito/401) por archive_jp_public_index.json
        try:
            jp_pub_idx_path = STATE_DIR / "archive_jp_public_index.json"
            if jp_pub_idx_path.exists():
                with open(jp_pub_idx_path, "r", encoding="utf-8") as f:
                    jp_pub_idx = json.load(f)

                # 0a: lookup por SERIAL (match exato)
                serial_index = jp_pub_idx.get("serial_index", {})
                if serial in serial_index:
                    entry = serial_index[serial]
                    identifier = entry["identifier"]
                    filename = entry["filename"]
                    encoded_filename = quote(filename, safe="/")
                    download_url = f"http://archive.org/download/{identifier}/{encoded_filename}"
                    log.info(f"JP public index hit (serial): {serial} -> {download_url[:100]}")
                    return ("direct_url", download_url), f"JP public index: {entry.get('title', '')[:60]}"

                # 0b: lookup por NOME normalizado (fallback)
                name_index = jp_pub_idx.get("name_index", {})
                search_norm = normalize_for_match(name)
                if search_norm in name_index:
                    entry = name_index[search_norm]
                    identifier = entry["identifier"]
                    filename = entry["filename"]
                    encoded_filename = quote(filename, safe="/")
                    download_url = f"http://archive.org/download/{identifier}/{encoded_filename}"
                    log.info(f"JP public index hit (name): {serial} -> {download_url[:100]}")
                    return ("direct_url", download_url), f"JP public index: {entry.get('title', '')[:60]}"
                else:
                    # Fuzzy match por palavras (bidirecional + validacao de numeros)
                    search_words = set(search_norm.split())
                    if not search_words:
                        pass
                    else:
                        best_match = None
                        best_score = 0
                        for idx_name, entry in name_index.items():
                            idx_words = set(idx_name.split())
                            if not idx_words:
                                continue
                            common = search_words & idx_words
                            if not common:
                                continue
                            # F1-score bidirecional
                            recall = len(common) / len(search_words)
                            precision = len(common) / len(idx_words)
                            score = 2 * recall * precision / (recall + precision) if (recall + precision) else 0
                            if score < 0.8 or score <= best_score:
                                continue
                            best_score = score
                            best_match = entry
                        if best_match:
                            identifier = best_match["identifier"]
                            filename = best_match["filename"]
                            encoded_filename = quote(filename, safe="/")
                            download_url = f"http://archive.org/download/{identifier}/{encoded_filename}"
                            log.info(f"JP public index hit (fuzzy): {serial} -> {download_url[:100]}")
                            return ("direct_url", download_url), f"JP public index: {best_match.get('title', '')[:60]}"
        except Exception as e:
            log.debug(f"jp_public_index erro: {e}")

        # Estrategia 0b: colecoes JP especificas do archive.org com nome do jogo
        # Todas as 4 colecoes originais sao access-restricted (exigem login) — filtrar.
        JP_COLLECTIONS = [c for c in ["PS1_JP_Arquivista", "PS1_JP_CHD_Arquivista", "chd_psx_jap", "chd_psx_jap_p2"]
                          if c not in ARCHIVE_RESTRICTED_COLLECTIONS]

        def search_collection(collection, q):
            query_str = f"collection:{collection} AND ({q}) AND mediatype:software"
            search_url = (
                f"https://archive.org/advancedsearch.php?q={quote_plus(query_str)}"
                f"&fl[]=identifier&fl[]=title&fl[]=downloads&rows=10&page=1&output=json"
            )
            try:
                resp = archive_request("get", search_url, timeout=(30, 180), headers=req_headers)
                if resp.status_code == 200:
                    return resp.json().get("response", {}).get("docs", [])
            except Exception:
                pass
            return []

        try:
            name_clean = re.sub(r"\(.*?\)", "", name).strip()
            name_clean = re.sub(r"\[.*?\]", "", name_clean).strip()
            # Manter apenas palavras significativas (remover termos genericos)
            name_words = [w for w in name_clean.split() if w.lower() not in {"the", "a", "an", "and", "of", "for", "in", "on", "with"}]
            search_title = " ".join(name_words[:4])

            for collection in JP_COLLECTIONS:
                docs = search_collection(collection, search_title)
                for doc in docs:
                    if doc["identifier"] in blacklisted_ids:
                        continue
                    title = doc.get("title", "").lower()
                    if any(term in title for term in blacklist_terms):
                        continue
                    # Verificar se o titulo bate razoavelmente com o nome
                    title_words = set(title.replace("(", " ").replace(")", " ").replace("-", " ").lower().split())
                    match_count = sum(1 for w in name_words if w.lower() in title_words)
                    if match_count >= max(1, len(name_words) // 3):
                        log.info(f"JP-collection hit: {serial} -> {doc['identifier']}")
                        return ("archive_item", doc["identifier"]), f"archive_jp.{collection}: {doc.get('title', '')[:50]}"

            # Estrategia 1: serial sem hifen (SLPS02000) — alguns itens do archive usam esse formato
            serial_nohyphen = serial.replace("-", "")
            docs = search_a(f"{serial_nohyphen} playstation")
            for doc in docs:
                if doc["identifier"] in blacklisted_ids:
                    continue
                ident_lower = doc["identifier"].lower().replace("-", "").replace("_", "")
                if serial_nohyphen.lower() in ident_lower:
                    title = doc.get("title", "").lower()
                    if not any(term in title for term in blacklist_terms):
                        return ("archive_item", doc["identifier"]), f"archive_jp: {doc.get('title', '')[:40]}"

            # Estrategia 2: serial com underscore (SLPS_02000) — formato redump
            serial_underscore = serial.replace("-", "_")
            docs = search_a(f"psx {serial_underscore}")
            for doc in docs:
                if doc["identifier"] in blacklisted_ids:
                    continue
                ident_lower = doc["identifier"].lower()
                if serial_underscore.lower() in ident_lower:
                    return ("archive_item", doc["identifier"]), f"archive_jp: {doc.get('title', '')[:40]}"

            # Estrategia 3: nome + Japan (muitos itens JP tem "Japan" no titulo)
            name_clean = re.sub(r"\(.*?\)", "", name).strip()
            name_clean = re.sub(r"\[.*?\]", "", name_clean).strip()
            if len(name_clean) > 3:
                docs = search_a(f'"{name_clean}" Japan playstation')
                for doc in docs:
                    if doc["identifier"] in blacklisted_ids:
                        continue
                    title = doc.get("title", "").lower()
                    if any(term in title for term in blacklist_terms):
                        continue
                    if "japan" in title or "j" in title.split() or serial.lower().replace("-","") in doc["identifier"].lower().replace("-","").replace("_",""):
                        return ("archive_item", doc["identifier"]), f"archive_jp: {doc.get('title', '')[:40]}"

            # Estrategia 4: nome em romaji + iso (formato comum em colecoes JP)
            if len(name_clean) > 3:
                docs = search_a(f"{name_clean} japan iso")
                name_words = [w for w in name_clean.lower().split() if len(w) > 2]
                for doc in docs:
                    if doc["identifier"] in blacklisted_ids:
                        continue
                    title = doc.get("title", "").lower()
                    if any(term in title for term in blacklist_terms):
                        continue
                    score = sum(1 for w in name_words if w in title)
                    if score >= max(1, len(name_words) // 2) and ("japan" in title or "jp" in title):
                        return ("archive_item", doc["identifier"]), f"archive_jp: {doc.get('title', '')[:40]}"

            return None, "archive_jp: nao encontrado"
        except Exception as e:
            return None, f"archive_jp: erro {e}"

    @staticmethod
    def _known_sites_map():
        return {
            "romspedia.com": "romspedia",
            "romsgames.net": "romsgames",
            "retromania.gg": "retromania",
            "romsfun.com": "romsfun",
            "romhustler.org": "romhustler",
            "coolrom.com": "coolrom",
            "retrostic.com": "retrostic",
            "cdromance.org": "cdromance",
            "vimm.net": "vimm",
            "archive.org": "archive_org",
            "myrient.erista.me": "myrient",
            "myrient.romhacking.net": "myrient",
            "romspack.com": "romspack",
            "totalroms.com": "totalroms",
            "romspure.cc": "romspure",
            "roms2000.com": "roms2000",
            "classicgames.me": "classicgames",
            "retrobit.net": "retrobit",
            "freeroms.com": "freeroms",
            "emuparadise.me": "emuparadise",
            "romulation.org": "romulation_org",
            "romsbase.com": "romsbase",
            "roms-download.com": "romsdl",
            "blueroms.com": "blueroms",
            "romsretro.com": "romsretro",
            "hexrom.net": "hexrom",
            "consoleroms.com": "consoleroms",
            "edgeemu.net": "edgeemu",
            "playretrogames.com": "playretrogames",
            "oldiesnest.com": "oldiesnest",
            "retrogametalk.com": "retrogametalk",
        }

    @staticmethod
    def _extract_known_urls(html, serial):
        """Extrai URLs de sites conhecidos a partir de HTML de buscador."""
        urls_found = []
        for domain, site_key in SiteNavigator._known_sites_map().items():
            pattern = rf'https?://(?:www\.)?{re.escape(domain)}/[^"\'<>\s]+'
            for match in re.finditer(pattern, html, re.IGNORECASE):
                url = match.group(0)
                skip_patterns = ["/emulators/", "/bios", "/contact", "/privacy", "/terms",
                                 "/about", "/blog", "/category/", "/tag/", "/page/",
                                 "/search", "/browse-all", "/requires-rom", "/download-limit"]
                if any(sp in url.lower() for sp in skip_patterns):
                    continue
                if serial.lower() in url.lower() or "rom" in url.lower() or "playstation" in url.lower():
                    urls_found.append((site_key, url))
        return urls_found

    @staticmethod
    def _follow_url_to_download(url, serial, req_headers):
        """Entra numa URL de site conhecido e extrai link direto de download."""
        try:
            resp2 = requests.get(url, timeout=5, headers=req_headers, allow_redirects=True)
            if resp2.status_code != 200:
                return None
            soup2 = BeautifulSoup(resp2.text, "lxml")
            for a2 in soup2.find_all("a", href=True):
                href = a2["href"]
                href_lower = href.lower()
                text_lower = a2.get_text(strip=True).lower()
                is_dl = ("download" in href_lower or "download" in text_lower or
                         ".zip" in href_lower or ".7z" in href_lower or
                         ".rar" in href_lower or ".iso" in href_lower)
                if is_dl:
                    dl_url = href if href.startswith("http") else (
                        f"https://{url.split('/')[2]}{href}" if href.startswith("/") else
                        f"{url.rsplit('/',1)[0]}/{href}"
                    )
                    if "archive.org" in dl_url:
                        return ("archive_item", dl_url)
                    return ("direct_url", dl_url)
        except Exception:
            pass
        return None

    def search_google(self, query, serial, name):
        """Busca ROMs PSX usando Bing e DuckDuckGo lite (ambos funcionam sem captcha).
        Google retorna 429; DuckDuckGo HTML endpoint esta morto.
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not serial:
            return None, "google: sem serial"

        def try_urls(urls_found, source_name):
            for site_key, url in urls_found[:5]:
                sub = self._follow_url_to_download(url, serial, req_headers)
                if sub:
                    kind, dl_url = sub
                    return (kind, dl_url, site_key), f"{source_name}->{site_key}: {serial}"
            return None, None

        search_query = f'"{serial}" psx rom download'

        # 1) Bing (retorna 200 com resultados)
        try:
            bing_url = f"https://www.bing.com/search?q={quote_plus(search_query)}&count=20"
            resp = requests.get(bing_url, timeout=10, headers=req_headers)
            if resp.status_code == 200:
                urls_found = self._extract_known_urls(resp.text, serial)
                if urls_found:
                    result, _ = try_urls(urls_found, "bing")
                    if result:
                        return result, f"bing: {serial}"
        except Exception as e:
            log.debug(f"Bing falhou: {e}")

        # 2) DuckDuckGo lite (funciona, sem captcha)
        try:
            suffixes = ["psx ps1 rom download", "psx iso", "playstation rom", "ps1 game iso download"]
            suffix = suffixes[hash(serial) % len(suffixes)]
            ddg_url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(serial + ' ' + suffix)}"
            resp = requests.get(ddg_url, timeout=10, headers=req_headers)
            if resp.status_code == 200:
                html = resp.text
                # DDG lite usa redirect em links: //duckduckgo.com/l/?uddg=URL
                for match in re.finditer(r'uddg=([^&\"\'<>\s]+)', html, re.IGNORECASE):
                    real_url = urllib.parse.unquote(match.group(1))
                    if "duckduckgo" not in real_url.lower():
                        html += "\n" + real_url
                urls_found = self._extract_known_urls(html, serial)
                if urls_found:
                    result, _ = try_urls(urls_found, "ddg")
                    if result:
                        return result, f"ddg: {serial}"
        except Exception as e:
            log.debug(f"DDG lite falhou: {e}")

        return None, "bing/ddg: nenhuma URL relevante encontrada"

    def search_homebrew(self, query, serial, name):
        """Busca homebrew PS1 — fontes: archive.org (psx-homebrew-library), DuckDuckGo (itch.io, github, etc).
        Homebrews geralmente estao em plataformas independentes; archive.org e o unico confiavel sem login.
        Estrategia: 1) archive.org psx-homebrew-library por nome; 2) DuckDuckGo para outras fontes.
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not name:
            return None, "homebrew: sem nome"
        # 1) Consultar indice local de homebrews (homebrew_index.json)
        try:
            idx_path = STATE_DIR / "homebrew_index.json"
            if idx_path.exists():
                idx = json.loads(idx_path.read_text(encoding="utf-8"))
                entry = idx.get(serial)
                if entry and entry.get("urls"):
                    urls = entry["urls"]
                    etype = entry.get("type", "direct_url")
                    if etype in ("direct_zip", "direct_chd"):
                        return ("direct_url", urls[0]), f"homebrew index: {entry.get('name', name)}"
                    elif etype == "github_release_assets":
                        # Baixar .cue (pequeno) e depois o .bin (sistema download_direct_url baixa um por vez)
                        # Retorna o primeiro URL; o downloader pega .cue, depois reprocessa .bin
                        return ("direct_url", urls[0]), f"homebrew index: {entry.get('name', name)}"
        except Exception as e:
            log.debug(f"homebrew index erro: {e}")

        # Usar nome curto (sem parenteses/colchetes) para busca
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        short_name = re.sub(r"\[.*?\]", "", short_name).strip()
        try:
            # 2) Buscar via DuckDuckGo Lite (sem JS, sem captcha, mais estavel)
            search_terms = [
                f'"{short_name}" ps1 homebrew download',
                f'"{short_name}" psx homebrew download',
                f'"{short_name}" ps1 homebrew rom',
                f'"{short_name}" psx homebrew bin',
                f'{short_name} ps1 homebrew',
            ]
            for ddg_query in search_terms:
                ddg_url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(ddg_query)}"
                resp = requests.get(ddg_url, timeout=15, headers=req_headers)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                # Extrair URLs reais do redirect DDG
                results = []
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True)
                    real_url = None
                    if "uddg=" in href:
                        real_url = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                    elif href.startswith("http") and "duckduckgo" not in href:
                        real_url = href
                    if real_url and text and len(text) > 3 and "duckduckgo" not in real_url.lower():
                        results.append((real_url, text))
                # Sites comuns de homebrew PS1 (prioridade)
                known_domains = {
                    "itch.io": "itch.io",
                    "github.com": "github.com",
                    "archive.org": "archive.org",
                    "psx-place.com": "psx_place",
                    "psxhomebrewgames.com": "psxhomebrewgames",
                    "psxdev.net": "psxdev",
                    "gbatemp.net": "gbatemp",
                    "romhacking.net": "romhacking",
                    "gamejolt.com": "gamejolt",
                    "indiedb.com": "indiedb",
                }
                urls_found = []
                for url, text in results:
                    domain = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
                    for known, key in known_domains.items():
                        if known in domain:
                            urls_found.append((key, url))
                            break
                    else:
                        # Aceitar tambem sites genericos com extensao de ROM na URL
                        if any(ext in url.lower() for ext in [".zip", ".7z", ".rar", ".bin", ".iso", ".cue", ".pbp"]):
                            urls_found.append((domain, url))
                # Tentar cada URL encontrada
                for site_key, url in urls_found[:8]:
                    try:
                        if site_key == "itch.io":
                            # itch.io: pagina do jogo -> POST /download_url -> URL temporaria
                            r2 = requests.get(url, timeout=5, headers=req_headers, allow_redirects=True)
                            if r2.status_code != 200:
                                continue
                            soup2 = BeautifulSoup(r2.text, "lxml")
                            upload_id = None
                            for tag in soup2.find_all(attrs={"data-upload_id": True}):
                                upload_id = tag.get("data-upload_id")
                                break
                            csrf = ""
                            for meta in soup2.find_all("meta"):
                                if meta.get("name") == "csrf-token":
                                    csrf = meta.get("content", "")
                            if upload_id and csrf:
                                post_url = url.rstrip("/") + "/download_url"
                                r3 = requests.post(post_url, data={"csrf_token": csrf, "upload_id": upload_id}, timeout=10, headers={**req_headers, "X-Requested-With": "XMLHttpRequest", "Referer": url})
                                if r3.status_code == 200:
                                    try:
                                        r3_data = r3.json()
                                        dl_url = r3_data.get("url", "")
                                    except Exception:
                                        dl_url = r3.text.strip()
                                    if dl_url.startswith("http"):
                                        # Verificar se o download e realmente um arquivo (nao pagina de login)
                                        r4 = requests.get(dl_url, timeout=10, headers=req_headers, stream=True)
                                        ct = r4.headers.get("content-type", "")
                                        if ct.startswith("application/") or any(r4.url.lower().endswith(ext) for ext in [".zip", ".7z", ".rar"]):
                                            return ("direct_url", r4.url), f"homebrew itch.io: {name}"
                                        # Se retornou HTML, exige login — deixa o browser tentar resolver (pode haver sessao)
                                        log.debug(f"homebrew itch.io requer login, devolvendo page_url: {name}")
                                        return ("page_url", url), f"homebrew itch.io (login?): {name}"
                        elif site_key == "github.com":
                            # Extrair user/repo do URL
                            m = re.search(r'github\.com/([^/]+)/([^/]+)', url)
                            if m:
                                user, repo = m.group(1), m.group(2)
                                repo = repo.split('?')[0].split('#')[0]
                                # Usar API do GitHub para obter assets da ultima release
                                api_url = f"https://api.github.com/repos/{user}/{repo}/releases/latest"
                                try:
                                    r_api = requests.get(api_url, timeout=10, headers={**req_headers, "Accept": "application/vnd.github+json"})
                                    if r_api.status_code == 200:
                                        release = r_api.json()
                                        tag = release.get("tag_name", "")
                                        for asset in release.get("assets", []):
                                            aname = asset.get("name", "")
                                            if any(aname.lower().endswith(ext) for ext in [".zip", ".7z", ".rar", ".bin", ".iso", ".cue", ".pbp"]):
                                                dl_url = asset.get("browser_download_url", "")
                                                if dl_url:
                                                    return ("direct_url", dl_url), f"homebrew github: {aname}"
                                except Exception as e:
                                    log.debug(f"homebrew github api erro: {e}")
                            # Fallback: pagina HTML (raramente tem links diretos sem JS)
                            r2 = requests.get(url, timeout=5, headers=req_headers)
                            if r2.status_code == 200:
                                soup2 = BeautifulSoup(r2.text, "lxml")
                                for a in soup2.find_all("a", href=True):
                                    href = a["href"]
                                    if "/releases/download/" in href and any(ext in href.lower() for ext in [".zip", ".7z", ".rar", ".bin", ".iso", ".cue", ".pbp"]):
                                        dl_url = href if href.startswith("http") else f"https://github.com{href}"
                                        return ("direct_url", dl_url), f"homebrew github: {name}"
                        elif site_key == "archive.org":
                            m = re.search(r'archive\.org/details/([^/\s]+)', url)
                            if not m:
                                m = re.search(r'archive\.org/download/([^/\s]+)', url)
                            if m:
                                identifier = m.group(1)
                                meta_url = f"https://archive.org/metadata/{identifier}"
                                r2 = archive_request("get", meta_url, timeout=(30, 180), headers=req_headers)
                                if r2.status_code == 200:
                                    data = r2.json()
                                    for f in data.get("files", []):
                                        fname = f.get("name", "")
                                        if any(fname.lower().endswith(ext) for ext in [".zip", ".7z", ".rar", ".bin", ".iso", ".cue", ".pbp"]):
                                            dl_url = f"http://archive.org/download/{identifier}/{requests.utils.quote(fname, safe='/')}"
                                            return ("direct_url", dl_url), f"homebrew archive.org: {name}"
                        elif site_key in ("psx_place", "psxhomebrewgames", "psxdev", "gbatemp", "romhacking", "gamejolt", "indiedb"):
                            # Sites JS-heavy ou com paywall: retornar page_url para browser tentar
                            return ("page_url", url), f"homebrew {site_key}: {name}"
                        else:
                            # Sites genericos: visitar pagina e procurar link de download
                            r2 = requests.get(url, timeout=5, headers=req_headers, allow_redirects=True)
                            if r2.status_code != 200:
                                continue
                            soup2 = BeautifulSoup(r2.text, "lxml")
                            for a in soup2.find_all("a", href=True):
                                href = a["href"]
                                text = a.get_text(strip=True).lower()
                                if "download" in text or any(ext in href.lower() for ext in [".zip", ".7z", ".rar", ".bin", ".iso", ".cue", ".pbp"]):
                                    dl_url = href if href.startswith("http") else (
                                        f"https://{url.split('/')[2]}{href}" if href.startswith("/") else f"{url.rsplit('/',1)[0]}/{href}"
                                    )
                                    return ("direct_url", dl_url), f"homebrew {site_key}: {name}"
                    except Exception as e:
                        log.debug(f"homebrew {site_key} erro: {e}")
                        continue
            return None, "homebrew: nao encontrado"
        except Exception as e:
            return None, f"homebrew: erro {e}"

    def search_archive_org(self, query, serial, name):
        """Busca no archive.org — estrategia: serial primeiro (preciso), nome depois (fallback)."""
        # Filtrar resultados irrelevantes
        blacklist_terms = ["cover", "manual", "art", "scans", "booklet", "insert", "psxtools", "psx_covers"]
        blacklisted_ids = set(load_blacklist().get("archive_ids", []))

        # Colecoes do archive.org que exigem login (access-restricted-item=true).
        # Todas as colecoes do archive_jp_name_index.json sao restritas — download
        # direto retorna HTTP 401. Precisamos pular essas entradas e cair para
        # estrategias que usam colecoes publicas (psx-chd-roms-*, Redump_*, etc).
        ARCHIVE_RESTRICTED_COLLECTIONS = {
            "PS1_JP_Arquivista",
            "PS1_JP_CHD_Arquivista",
            "chd_psx_jap",
            "chd_psx_jap_p2",
        }

        # Estrategia 0: indice JP publico pre-construido (lookup local, instantaneo)
        # Substitui archive_jp_index.json + archive_jp_name_index.json (ambos restritos/401).
        # Novo indice: archive_jp_public_index.json com serial_index e name_index.
        jp_pub_idx_path = STATE_DIR / "archive_jp_public_index.json"
        if jp_pub_idx_path.exists():
            try:
                jp_pub_idx = json.loads(jp_pub_idx_path.read_text(encoding="utf-8"))

                # 0a: lookup por SERIAL (match exato)
                if is_real_serial(serial) and serial in jp_pub_idx.get("serial_index", {}):
                    entry = jp_pub_idx["serial_index"][serial]
                    identifier = entry["identifier"]
                    filename = entry["filename"]
                    encoded_filename = quote(filename, safe="/")
                    download_url = f"http://archive.org/download/{identifier}/{encoded_filename}"
                    log.info(f"JP public index hit (serial): {serial} -> {download_url[:100]}")
                    return ("direct_url", download_url), f"JP public index: {entry.get('title', '')[:60]}"

                # 0b: lookup por NOME normalizado (fallback quando serial nao encontrado)
                if serial and serial.startswith(("SLPS", "SLPM", "SCPS", "SLKA")) and name:
                    name_index = jp_pub_idx.get("name_index", {})
                    # Normalizar nome igual a construcao do indice:
                    # remover (parens) e [brackets], lowercase, non-word -> espacos, collapse
                    name_norm = re.sub(r"\(.*?\)", "", name)
                    name_norm = re.sub(r"\[.*?\]", "", name_norm)
                    name_norm = name_norm.lower()
                    name_norm = re.sub(r"[^a-z0-9\s]", " ", name_norm)
                    name_norm = re.sub(r"\s+", " ", name_norm).strip()
                    if name_norm in name_index:
                        entry = name_index[name_norm]
                        identifier = entry["identifier"]
                        filename = entry["filename"]
                        encoded_filename = quote(filename, safe="/")
                        download_url = f"http://archive.org/download/{identifier}/{encoded_filename}"
                        log.info(f"JP public index hit (name): {serial} -> {download_url[:100]}")
                        return ("direct_url", download_url), f"JP public index: {entry.get('title', '')[:60]}"
                    else:
                        log.debug(f"JP public index miss (name): {serial} (key={name_norm[:60]})")
                elif is_real_serial(serial):
                    log.debug(f"JP public index miss (serial): {serial}")
            except Exception as e:
                log.warning(f"jp_public_index erro: {e}")

        def search_archive(query_str, rows=50):
            search_url = (
                f"https://archive.org/advancedsearch.php?q={quote_plus(query_str)}"
                f"+AND+mediatype%3Asoftware&fl[]=identifier&fl[]=title&fl[]=downloads"
                f"&rows={rows}&page=1&output=json"
            )
            try:
                resp = archive_request("get", search_url, timeout=(10, 45), headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200:
                    return []
                return resp.json().get("response", {}).get("docs", [])
            except Exception:
                return []

        def is_blacklisted_doc(doc):
            title = doc.get("title", "").lower()
            ident = doc.get("identifier", "").lower()
            return any(term in title or term in ident for term in blacklist_terms)

        real_serial = is_real_serial(serial)

        # Preparar palavras do nome
        name_clean = re.sub(r"\(.*?\)", "", (name or "")).strip()
        name_norm = name_clean.lower().replace("-", " ")
        name_words = [w for w in re.sub(r"[^a-z0-9\s]", "", name_norm).split() if len(w) > 2]

        # Estrategia 1: serial entre aspas
        if real_serial:
            docs = search_archive(f'"{serial}"')
            if docs:
                for doc in docs:
                    if doc["identifier"] in blacklisted_ids:
                        continue
                    title = doc.get("title", "").lower()
                    if any(term in title for term in blacklist_terms):
                        continue
                    ident_lower = doc["identifier"].lower().replace("-", "").replace("_", "")
                    serial_lower = serial.lower().replace("-", "")
                    title_lower = title.replace("-", "").replace(" ", "")
                    if serial_lower in ident_lower or serial_lower in title_lower:
                        return ("archive_item", doc["identifier"]), f"archive.org: {doc.get('title', '')}"

        # PULAR estrategia 2 (serial sem aspas) — raramente funciona e custa 10s

            # Estrategia 3: nome do jogo + psx
            name_clean = re.sub(r"\(.*?\)", "", name).strip()
            # Normalizar: hifens viram espacos, remover pontuacao
            name_norm = name_clean.lower().replace("-", " ")
            name_words = [w for w in re.sub(r"[^a-z0-9\s]", "", name_norm).split() if len(w) > 2]
            if name_words:  # Permitir mesmo 1 palavra (antes exigia >= 2)
                docs = search_archive(f"{name_clean} psx playstation")
                if docs:
                    for doc in docs:
                        if doc["identifier"] in blacklisted_ids:
                            continue
                        title = doc.get("title", "").lower()
                        # Normalizar titulo tambem (hifens -> espacos)
                        title_norm = title.replace("-", " ")
                        if any(term in title for term in blacklist_terms):
                            continue
                        # Score por palavras do nome (usar titulo normalizado)
                        score = sum(1 for w in name_words if w in title_norm)
                        # Score minimo: pelo menos 1 palavra OU 50% das palavras
                        min_score = max(1, len(name_words) // 2)
                        if score >= min_score:
                            return ("archive_item", doc["identifier"]), f"archive.org: {doc.get('title', '')}"

            # Estrategia 4: buscar por psx_ + serial (padrao de itens individuais do archive.org)
            if serial:
                serial_clean = serial.lower().replace("-", "_")
                docs = search_archive(f"psx_{serial_clean}")
                if docs:
                    for doc in docs:
                        if doc["identifier"] in blacklisted_ids:
                            continue
                        ident_lower = doc["identifier"].lower()
                        if serial_lower in ident_lower.replace("-", "").replace("_", ""):
                            return ("archive_item", doc["identifier"]), f"archive.org: {doc.get('title', '')}"

            # Estrategia 5: buscar em colecao redump (psx-redump-NNNNN-SLPS-XXXXX)
            if serial:
                docs = search_archive(f"redump {serial}")
                if docs:
                    for doc in docs:
                        if doc["identifier"] in blacklisted_ids:
                            continue
                        ident_lower = doc["identifier"].lower().replace("-", "").replace("_", "")
                        serial_lower_clean = serial.lower().replace("-", "")
                        if serial_lower_clean in ident_lower:
                            return ("archive_item", doc["identifier"]), f"archive.org: {doc.get('title', '')}"

            # Estrategia 6: buscar por nome sem "psx" (jogos japoneses podem estar com nome em romaji)
            if len(name_words) >= 2:
                docs = search_archive(f"{name_clean} playstation")
                if docs:
                    for doc in docs:
                        if doc["identifier"] in blacklisted_ids:
                            continue
                        title = doc.get("title", "").lower()
                        if any(term in title for term in blacklist_terms):
                            continue
                        score = sum(1 for w in name_words if w in title)
                        if score >= max(2, len(name_words) // 2):
                            return ("archive_item", doc["identifier"]), f"archive.org: {doc.get('title', '')}"

            # Estrategia 7: buscar por primeiras 2-3 palavras do nome (para nomes longos japoneses)
            if len(name_words) >= 3:
                short_name = " ".join(name_words[:3])
                docs = search_archive(f"{short_name} psx")
                if docs:
                    for doc in docs:
                        if doc["identifier"] in blacklisted_ids:
                            continue
                        title = doc.get("title", "").lower()
                        if any(term in title for term in blacklist_terms):
                            continue
                        score = sum(1 for w in name_words[:3] if w in title)
                        if score >= 2:
                            return ("archive_item", doc["identifier"]), f"archive.org: {doc.get('title', '')}"

            # Estrategia 7.5: buscar na colecao psxrip (arquivos .paq9a por serial)
            if serial:
                serial_clean = serial.replace("-", "").replace("_", "")
                docs = search_archive(f"psxrip {serial}")
                if docs:
                    for doc in docs:
                        if doc["identifier"] in blacklisted_ids:
                            continue
                        title = doc.get("title", "").lower()
                        if any(term in title for term in blacklist_terms):
                            continue
                        # O arquivo na colecao psxrip tem o serial no nome
                        ident = doc["identifier"].lower()
                        if serial_clean in ident.replace("-", "").replace("_", ""):
                            return ("archive_item", doc["identifier"]), f"archive.org: {doc.get('title', '')}"

            # Estrategia 8: buscar sem mediatype filter (alguns itens podem nao estar classificados)
            if serial:
                try:
                    search_url2 = (
                        f"https://archive.org/advancedsearch.php?q={quote_plus(serial)}"
                        f"&fl[]=identifier&fl[]=title&fl[]=downloads"
                        f"&rows=50&page=1&output=json"
                    )
                    resp2 = archive_request("get", search_url2, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                    if resp2.status_code == 200:
                        docs2 = resp2.json().get("response", {}).get("docs", [])
                        for doc in docs2:
                            if doc["identifier"] in blacklisted_ids:
                                continue
                            ident_lower = doc["identifier"].lower().replace("-", "").replace("_", "")
                            serial_lower2 = serial.lower().replace("-", "")
                            if serial_lower2 in ident_lower:
                                title = doc.get("title", "").lower()
                                if not any(term in title for term in blacklist_terms):
                                    return ("archive_item", doc["identifier"]), f"archive.org: {doc.get('title', '')}"
                except Exception:
                    pass

            return None, "archive.org: sem resultados"

    def download_archive_item(self, identifier, serial, name):
        global _ARCHIVE_METADATA_CACHE
        with _ARCHIVE_METADATA_LOCK:
            data = _ARCHIVE_METADATA_CACHE.get(identifier)
        if data is None:
            metadata_url = f"https://archive.org/metadata/{identifier}"
            try:
                resp = archive_request("get", metadata_url, timeout=30)
                if resp.status_code != 200:
                    return None, f"archive metadata HTTP {resp.status_code}"
                data = resp.json()
                with _ARCHIVE_METADATA_LOCK:
                    _ARCHIVE_METADATA_CACHE[identifier] = data
            except Exception as e:
                return None, f"archive metadata erro: {str(e)[:100]}"
            # Verificar titulo do item contra serial/nome esperado
            item_title = data.get("metadata", {}).get("title", "").lower()
            serial_lower = (serial or "").lower().replace("-", "")
            name_clean = re.sub(r"\(.*?\)", "", (name or "")).strip().lower()
            name_words = [w for w in re.sub(r"[^a-z0-9\s]", "", name_clean).split() if len(w) > 2]
            # Se o titulo nao contem o serial nem nenhuma palavra do nome, suspeito
            title_no_special = item_title.replace("-", "").replace("_", "").replace(" ", "")
            title_matches = (serial_lower in title_no_special) if serial_lower else False
            if not title_matches and name_words:
                # Matching flexivel: palavra no titulo OU prefixo da palavra (ex: Ninku vs Ninkuu)
                def word_match(word, text):
                    if word in text:
                        return True
                    # Prefixo de 4+ chars (ex: "nink" em "ninku" e "ninkuu")
                    if len(word) >= 4 and word[:4] in text:
                        return True
                    return False
                # Matching rigoroso: pelo menos 80% das palavras significantes devem bater
                # Para evitar false positives com series (ex: "Simple 1500 Series vol.20" vs "vol.76")
                match_count = sum(1 for w in name_words if word_match(w, item_title))
                title_matches = match_count >= max(2, len(name_words) * 4 // 5)
                # Verificacao adicional: se ambos tem numero de volume, devem bater
                vol_match = True
                vol_expected = re.search(r"vol\.?\s*(\d+)", name_clean)
                vol_item = re.search(r"vol\.?\s*(\d+)", item_title)
                if vol_expected and vol_item:
                    vol_match = vol_expected.group(1) == vol_item.group(1)
                if not vol_match:
                    title_matches = False
            if not title_matches:
                log.warning(f"Titulo do item nao bate: '{item_title}' vs serial={serial} name={name}")
                # Blacklistar este identifier
                bl = load_blacklist()
                add_to_blacklist(bl, url=identifier, reason=f"titulo nao bate: {item_title[:60]} vs {serial}")
                return None, f"archive.org: titulo nao corresponde ({item_title[:40]})"

            files = data.get("files", [])
            rom_files = []
            for f in files:
                fname = f.get("name", "")
                fext = Path(fname).suffix.lower()
                if fext in ROM_EXTS or fext in ARCHIVE_EXTS:
                    size = int(f.get("size", 0))
                    # Filtrar arquivos muito pequenos (< 1MB para ROMs)
                    if size > 1024 * 1024:
                        rom_files.append((fname, size, fext))
            if not rom_files:
                return None, "archive.org: sem ROMs no item"
            # Preferir arquivos que contenham o serial ou nome do jogo
            name_lower = name_clean
            best_files = []
            for fname, size, fext in rom_files:
                fname_lower = fname.lower().replace("-", "").replace("_", "").replace(" ", "")
                score = 0
                if serial_lower and serial_lower in fname_lower:
                    score += 10
                if name_words:
                    score += sum(1 for w in name_words if w in fname.lower())
                best_files.append((fname, size, fext, score))
            # Ordenar por score (desc) e depois por tamanho (desc)
            best_files.sort(key=lambda x: (x[3], x[1]), reverse=True)
            fname, size, fext, _ = best_files[0]
            dl_url = f"http://archive.org/download/{identifier}/{quote(fname, safe='/')}"
            dest = DOWNLOADS_TMP / f"{serial}_{fname}"
            log.info(f"Baixando via aria2c: {dl_url}")
            # Usar aria2c (multi-chunk 16 conexões, resume automático, retry infinito)
            result = _aria2_download(dl_url, dest, serial, expected_size=size, timeout=600)
            if result[0] is not None:
                dest, msg = result
                actual_size = dest.stat().st_size
                if actual_size < 1024 * 1024:  # Minimo 1MB
                    dest.unlink(missing_ok=True)
                    return None, f"download muito pequeno ({actual_size} bytes)"
                # Verificar se o tamanho baixado corresponde ao esperado
                if abs(actual_size - size) > 1024 and size > 0:
                    log.warning(f"Tamanho divergente: esperado {size}, baixado {actual_size}")
                return dest, msg
            else:
                return None, result[1]

    def download_direct_url(self, url, serial):
        # Detectar extensao correta a partir da URL ou Content-Disposition
        url_path = Path(url.split("?")[0]).name
        # Se o ultimo segmento nao tem extensao, tentar extrair do path anterior
        if "." not in url_path:
            # Procurar extensao no path da URL (ex: /roms/psx/Game.7z/hash/ts)
            parts = url.split("?")[0].split("/")
            for part in reversed(parts):
                if "." in part and not part.isdigit():
                    url_path = part
                    break
        dest = DOWNLOADS_TMP / f"{serial}_{url_path}"
        try:
            t0 = time.time()
            # Session com connection pooling — SEM retries do urllib3 (falha rapido)
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=50,
                pool_maxsize=50,
                max_retries=0,
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
            # romsbase fetch.php precisa de sessao + referer da pagina de download + headers completos
            if "romsbase.com/fetch.php" in url:
                rom_id = url.split("id=")[-1].split("&")[0]
                dl_page = f"https://www.romsbase.com/download/{rom_id}"
                try:
                    session.get(dl_page, headers=headers, timeout=15)
                    headers["Referer"] = dl_page
                except Exception:
                    pass

            # romsfun: pagina /1 contem link real para sto.romsfast.com
            if "romsfun.com/download/" in url and url.endswith("/1"):
                try:
                    r1 = session.get(url, headers=headers, timeout=15)
                    if r1.status_code == 200:
                        soup1 = BeautifulSoup(r1.text, "lxml")
                        real_link = None
                        for a in soup1.find_all("a", href=True):
                            text = a.get_text(strip=True).lower()
                            href = a["href"]
                            if ("download now" in text or "romsfast" in href.lower()) and href.startswith("http"):
                                real_link = href
                                break
                        if real_link:
                            url = real_link
                            headers["Referer"] = url
                            headers["Origin"] = "https://romsfun.com"
                            url_path = Path(real_link.split("?")[0]).name
                            dest = DOWNLOADS_TMP / f"{serial}_{url_path}"
                except Exception as e:
                    log.debug(f"romsfun resolve erro: {e}")
            # retroiso: redirect para Google Drive com virus scan warning
            if "retroiso.com/download/" in url:
                try:
                    r1 = session.get(url, headers=headers, timeout=15, allow_redirects=True)
                    if r1.status_code == 200 and "drive.usercontent.google.com" in r1.url:
                        soup1 = BeautifulSoup(r1.text, "lxml")
                        form = soup1.find("form")
                        if form:
                            data = {inp["name"]: inp.get("value", "") for inp in form.find_all("input") if inp.get("name")}
                            action = form.get("action")
                            if action and data.get("id"):
                                query = "&".join(f"{k}={v}" for k, v in data.items())
                                url = f"{action}?{query}"
                                url_path = f"{serial}.7z"
                                dest = DOWNLOADS_TMP / f"{serial}_{url_path}"
                except Exception as e:
                    log.debug(f"retroiso resolve erro: {e}")
            # vimm/archival.cat e lento — aumentar timeout
            # archive.org pode servir arquivos grandes: dar mais tempo
            if "archival.cat" in url:
                dl_timeout = 900
            elif "archive.org" in url:
                dl_timeout = 600
            else:
                dl_timeout = 300
            # ── Download via aria2c (multi-chunk 16 conexões, resume automático) ──
            log.info(f"Baixando via aria2c: {url}")
            result = _aria2_download(url, dest, serial, expected_size=0, timeout=dl_timeout)
            if result[0] is None:
                return None, result[1]
            dest = result[0]
            size = dest.stat().st_size
            if size < 1024:
                return None, "arquivo muito pequeno"
            # Detectar paginas de erro disfarcadas de ROM (romhustler/romsfun/romsbase)
            try:
                with open(dest, "rb") as fcheck:
                    header = fcheck.read(4096)
                if header.strip().startswith(b"<") or b"<html" in header.lower() or b"<script" in header.lower() or b"<!doctype" in header.lower():
                    try:
                        dest.unlink()
                    except Exception:
                        pass
                    return None, "download falso: pagina HTML disfarcada de ROM"
            except Exception:
                pass
            # romsbase: Myrient (backend) foi fechado em 31/03/2026 e
            # fetch.php retorna uma pagina HTML de erro disfarcada de ZIP
            if "romsbase.com" in url and is_romsbase_dead_page(dest):
                try:
                    dest.unlink()
                except Exception:
                    pass
                return None, "romsbase: backend Myrient encerrou (pagina de shutdown)"
            return dest, result[1]
        except Exception as e:
            return None, str(e)[:200]

    def download_via_browser(self, url, serial):
        """Download via browser — navega para a URL e espera o download iniciar.
        Suporta paginas com contador (ex: romspedia 6s) e redirects JS.
        """
        try:

            # itch.io: pagina do jogo -> botao Download -> modal -> clicar no primeiro link
            if "itch.io" in url:
                try:
                    self.page.goto(url, timeout=30000)
                    time.sleep(2)
                    # Clicar no botao/span com texto "Download"
                    download_btn = self.page.locator("button:has-text('Download'), a:has-text('Download'), span:has-text('Download')").first
                    if download_btn.count() > 0:
                        download_btn.click(timeout=10000)
                        time.sleep(2)
                        # Procurar links de download no modal (geralmente .zip)
                        for a in self.page.locator("a[href]").all():
                            href = a.get_attribute("href") or ""
                            text = (a.inner_text() or "").lower()
                            if "/download" in href or any(ext in href.lower() for ext in [".zip", ".7z", ".rar"]):
                                with self.page.expect_download(timeout=60000) as download_info:
                                    a.click(timeout=10000)
                                download = download_info.value
                                dest = DOWNLOADS_TMP / f"{serial}_{download.suggested_filename}"
                                download.save_as(str(dest))
                                return dest, f"baixado via browser (itch.io): {dest.name}"
                    # Se nao achou botao, tentar qualquer link de download
                    soup = BeautifulSoup(self.page.content(), "lxml")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if "/download" in href or any(ext in href.lower() for ext in [".zip", ".7z", ".rar"]):
                            dl_url = href if href.startswith("http") else f"https://itch.io{href}"
                            with self.page.expect_download(timeout=60000) as download_info:
                                self.page.goto(dl_url, timeout=30000)
                            download = download_info.value
                            dest = DOWNLOADS_TMP / f"{serial}_{download.suggested_filename}"
                            download.save_as(str(dest))
                            return dest, f"baixado via browser (itch.io link): {dest.name}"
                except Exception as e:
                    log.debug(f"itch.io browser erro: {e}")

            # romsbase: a pagina de download tem um link fetch.php — clicar nele e esperar o download
            if "romsbase.com/download/" in url:
                try:
                    self.page.goto(url, timeout=30000)
                    time.sleep(2)
                    # Procurar link fetch.php na pagina
                    fetch_link = None
                    for a in self.page.locator("a").all():
                        href = a.get_attribute("href") or ""
                        if "fetch.php" in href:
                            fetch_link = href
                            break
                    if fetch_link:
                        with self.page.expect_download(timeout=60000) as download_info:
                            a.click(timeout=10000)
                        download = download_info.value
                        dest = DOWNLOADS_TMP / f"{serial}_{download.suggested_filename}"
                        download.save_as(str(dest))
                        # romsbase: Myrient foi fechado; fetch.php retorna pagina de erro disfarcada de ZIP
                        if is_romsbase_dead_page(dest):
                            try:
                                dest.unlink()
                            except Exception:
                                pass
                            return None, "romsbase: backend Myrient encerrou (pagina de shutdown)"
                        return dest, f"baixado via browser (romsbase): {dest.name}"
                except Exception as e:
                    log.debug(f"romsbase browser click erro: {e}")
            # Navegar para a pagina
            self.page.goto(url, timeout=30000)
            # Esperar possivel contador/redirect (max 15s)
            time.sleep(3)
            # Procurar link de download direto na pagina (ex: downloads.romspedia.com)
            soup = BeautifulSoup(self.page.content(), "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                if any(kw in text for kw in ["click here", "download", "download here", "here"]):
                    if href.startswith("http") and "download" in href.lower():
                        # Link de download direto encontrado — baixar via requests
                        dl_resp = requests.get(href, timeout=45, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
                        if dl_resp.status_code == 200:
                            dest = DOWNLOADS_TMP / f"{serial}_{href.split('/')[-1].split('?')[0]}"
                            t0 = time.time()
                            total_size = int(dl_resp.headers.get("content-length", 0))
                            downloaded = 0
                            with open(dest, "wb") as f:
                                for chunk in dl_resp.iter_content(1024 * 1024):
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    now = time.time()
                                    elapsed_now = now - t0
                                    speed_now = downloaded / elapsed_now if elapsed_now > 0 else 0
                                    queue_update_progress(serial, downloaded, total_size, speed_now)
                            time.sleep(2)
                            queue_clear_progress(serial)
                            return dest, f"baixado via browser (link): {dest.name}"
            # Se nao achou link, tentar esperar download automatico
            try:
                with self.page.expect_download(timeout=30000) as download_info:
                    pass
                download = download_info.value
                dest = DOWNLOADS_TMP / f"{serial}_{download.suggested_filename}"
                download.save_as(str(dest))
                return dest, f"baixado via browser: {dest.name}"
            except Exception:
                pass
            # Ultima tentativa: esperar mais 10s e ver se URL mudou
            time.sleep(10)
            current_url = self.page.url
            if current_url != url and "download" in current_url.lower():
                dl_resp = requests.get(current_url, timeout=45, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
                if dl_resp.status_code == 200:
                    dest = DOWNLOADS_TMP / f"{serial}_{current_url.split('/')[-1].split('?')[0]}"
                    t0 = time.time()
                    total_size = int(dl_resp.headers.get("content-length", 0))
                    downloaded = 0
                    with open(dest, "wb") as f:
                        for chunk in dl_resp.iter_content(1024 * 1024):
                            f.write(chunk)
                            downloaded += len(chunk)
                            now = time.time()
                            elapsed_now = now - t0
                            speed_now = downloaded / elapsed_now if elapsed_now > 0 else 0
                            queue_update_progress(serial, downloaded, total_size, speed_now)
                    time.sleep(2)
                    queue_clear_progress(serial)
                    return dest, f"baixado via browser (redirect): {dest.name}"
            return None, "download via browser: sem download iniciado"
        except PWTimeout:
            return None, "timeout no download"
        except Exception as e:
            return None, str(e)[:200]

    def search_duckduckgo(self, query, serial, name):
        """Busca via DuckDuckGo (sem captcha) — descobre novos sites de ROM e os cadastra em sites.json."""
        # Variar o query para evitar padrao fixo
        query_suffixes = ["psx ps1 rom download", "psx iso", "playstation rom",
                          "psx rom free download", "ps1 game iso download"]
        suffix = query_suffixes[hash(serial) % len(query_suffixes)]
        # DuckDuckGo lite endpoint (html.duckduckgo.com esta morto)
        search_url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query + ' ' + suffix)}"
        ok, err = self._safe_goto(search_url)
        if not ok:
            return None, f"ddg: {err}"
        time.sleep(1)
        soup = BeautifulSoup(self.page.content(), "lxml")
        # DuckDuckGo HTML: links com class "result__a"
        results = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            # DuckDuckGo usa redirect: //duckduckgo.com/l/?uddg=URL
            if "uddg=" in href:
                real_url = href.split("uddg=")[1].split("&")[0]
                real_url = urllib.parse.unquote(real_url)
            elif href.startswith("http") and "duckduckgo" not in href:
                real_url = href
            else:
                continue
            if text and len(text) > 5 and "duckduckgo" not in real_url.lower():
                results.append((real_url, text))
        if not results:
            return None, "ddg: nenhum link"

        bl = load_blacklist()
        blacklisted_domains = set(bl.get("sites", []))
        blacklisted_urls = set(bl.get("urls", []))

        # === Descoberta de novos sites ===
        sites = load_sites()
        discovered_count = 0
        for url, text in results:
            parsed = urlparse(url)
            domain = parsed.netloc
            if not domain or "duckduckgo" in domain:
                continue
            site_key = domain.replace("www.", "").split(".")[0]
            if site_key in sites or site_key in blacklisted_domains:
                continue
            # Filtrar dominios nao-rom
            skip_domains = ["google", "youtube", "wikipedia", "reddit", "facebook",
                          "twitter", "amazon", "ebay", "pinterest", "instagram",
                          "tiktok", "stackoverflow", "github", "discord", "duckduckgo"]
            if any(d in domain for d in skip_domains):
                continue
            sites[site_key] = {
                "url": f"https://{domain}",
                "search_url": f"https://{domain}/?s={{query}}",
                "type": "direct_search",
                "enabled": True,
                "fail_count": 0,
                "max_fails": 50,
                "discovered": True,
                "discovered_from": "ddg",
            }
            discovered_count += 1
            log.info(f"Site descoberto: {site_key} -> {domain}")
        if discovered_count:
            save_sites(sites)

        # Filtrar resultados blacklisted
        filtered = [(u, t) for u, t in results
                    if urlparse(u).netloc.replace("www.", "").split(".")[0] not in blacklisted_domains
                    and u not in blacklisted_urls]

        # Procurar download direto nos resultados
        for url, text in filtered[:10]:
            if any(url.endswith(ext) for ext in ARCHIVE_EXTS):
                return ("direct_url", url), f"ddg: {text[:50]}"

        # Visitar sites encontrados procurando ROM
        rom_keywords = ["rom", "download", "iso", "psx", "ps1", "playstation", "game"]
        for url, text in filtered[:15]:
            text_lower = text.lower()
            url_lower = url.lower()
            if any(kw in text_lower or kw in url_lower for kw in rom_keywords):
                ok, err = self._safe_goto(url)
                if not ok:
                    if "paywall" in err or "bloqueado" in err or "malware" in err:
                        domain_key = urlparse(url).netloc.replace("www.", "").split(".")[0]
                        add_to_blacklist(load_blacklist(), site_key=domain_key,
                                       reason=f"ddg descobriu: {err}")
                    continue
                time.sleep(1)
                soup2 = BeautifulSoup(self.page.content(), "lxml")
                for a in soup2.find_all("a", href=True):
                    href = a["href"]
                    a_text = a.get_text(strip=True).lower()
                    if any(href.endswith(ext) for ext in ARCHIVE_EXTS):
                        return ("direct_url", urljoin(url, href)), f"ddg->site: {text[:50]}"
                    if "download" in a_text and href.startswith("http"):
                        return ("page_url", href), f"ddg->site: {text[:50]}"
        return None, "ddg: sem link util"

    # ============================================================
    # SITES DESCOBERTOS PELO AGENTE DE EXPLORACAO
    # ============================================================

    def search_myrient(self, query, serial, name):
        """Myrient foi desligado em 31/03/2026. Mantido como placeholder."""
        return None, "myrient: servico encerrado (31/03/2026)"

    def search_emuparadise(self, query, serial, name):
        """Busca no EmuParadise — retorna page_url para download via browser.
        Search: https://www.emuparadise.me/roms/search.php?query={query}&system=Sony+Playstation
        """
        if not name:
            return None, "emuparadise: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        short_name = re.sub(r"\[.*?\]", "", short_name).strip()
        search_url = f"https://www.emuparadise.me/roms/search.php?query={quote_plus(short_name)}&system=Sony+Playstation"
        req_headers = {"User-Agent": "Mozilla/5.0"}
        try:
            resp = requests.get(search_url, timeout=20, headers=req_headers)
            if resp.status_code != 200:
                return None, f"emuparadise: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            name_words = [w for w in short_name.lower().split() if len(w) > 2]
            best = None
            best_score = 0
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                if "/Sony_Playstation_ISOs/" not in href:
                    continue
                # Pontuar por palavras do nome e por regiao (serial prefixo)
                score = sum(1 for w in name_words if w in text)
                if serial and serial[:4].lower() in text:
                    score += 2
                if score > best_score:
                    best_score = score
                    best = (href, text)
            if best and best_score >= max(1, len(name_words) // 2):
                href, text = best
                url = href if href.startswith("http") else f"https://www.emuparadise.me{href}"
                return ("page_url", url), f"emuparadise: {text[:60]}"
            return None, "emuparadise: sem resultados"
        except Exception as e:
            return None, f"emuparadise: erro {e}"

    def search_romspack(self, query, serial, name):
        """Busca no RomsPack — lista de packs e single files, muitos apontam archive.org.
        Search: https://www.romspack.com/?s={query}
        """
        if not name:
            return None, "romspack: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        search_url = f"https://www.romspack.com/?s={quote_plus(short_name)}"
        req_headers = {"User-Agent": "Mozilla/5.0"}
        try:
            resp = requests.get(search_url, timeout=20, headers=req_headers)
            if resp.status_code != 200:
                return None, f"romspack: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                if "/ps1-roms-pack/" in href or "/psx/" in href or "/playstation/" in href:
                    if any(w in text for w in short_name.lower().split()[:3]):
                        url = href if href.startswith("http") else f"https://www.romspack.com{href}"
                        return ("page_url", url), f"romspack: {text[:60]}"
            return None, "romspack: sem resultados"
        except Exception as e:
            return None, f"romspack: erro {e}"

    def search_totalroms(self, query, serial, name):
        """Busca no TotalROMs."""
        if not name:
            return None, "totalroms: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        search_url = f"https://www.totalroms.com/?s={quote_plus(short_name)}"
        return self._generic_page_search("totalroms", search_url, short_name, serial)

    def search_romspure(self, query, serial, name):
        """Busca no ROMsPure."""
        if not name:
            return None, "romspure: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        search_url = f"https://romspure.cc/search?q={quote_plus(short_name)}"
        return self._generic_page_search("romspure", search_url, short_name, serial)

    def search_roms2000(self, query, serial, name):
        """Busca no ROMs2000."""
        if not name:
            return None, "roms2000: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        search_url = f"https://roms2000.com/?s={quote_plus(short_name)}"
        return self._generic_page_search("roms2000", search_url, short_name, serial)

    def search_classicgames(self, query, serial, name):
        """Busca no ClassicGames."""
        if not name:
            return None, "classicgames: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        search_url = f"https://classicgames.me/?s={quote_plus(short_name)}"
        return self._generic_page_search("classicgames", search_url, short_name, serial)

    def search_retrobit(self, query, serial, name):
        """Busca no Retro-Bit."""
        if not name:
            return None, "retrobit: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        search_url = f"https://retro-bit.ru/?s={quote_plus(short_name)}"
        return self._generic_page_search("retrobit", search_url, short_name, serial)

    def search_freeroms(self, query, serial, name):
        """Busca no FreeROMs — lista por letra."""
        if not serial:
            return None, "freeroms: sem serial"
        first_letter = serial[0].lower()
        list_url = f"https://www.freeroms.com/psx_{first_letter}.htm"
        req_headers = {"User-Agent": "Mozilla/5.0"}
        try:
            resp = requests.get(list_url, timeout=20, headers=req_headers)
            if resp.status_code != 200:
                return None, f"freeroms: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            name_lower = name.lower() if name else ""
            serial_lower = serial.lower()
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                href = a["href"]
                if serial_lower in text or (name_lower and any(w in text for w in name_lower.split()[:3])):
                    url = href if href.startswith("http") else f"https://www.freeroms.com/{href}"
                    return ("page_url", url), f"freeroms: {text[:60]}"
            return None, "freeroms: nao encontrado"
        except Exception as e:
            return None, f"freeroms: erro {e}"

    def _generic_page_search(self, site_key, search_url, short_name, serial):
        """Busca generica em site WordPress-like; retorna page_url se achar link plausivel."""
        req_headers = {"User-Agent": "Mozilla/5.0"}
        try:
            resp = requests.get(search_url, timeout=20, headers=req_headers)
            if resp.status_code != 200:
                return None, f"{site_key}: HTTP {resp.status_code}"
            soup = BeautifulSoup(resp.text, "lxml")
            name_words = short_name.lower().split()[:3]
            serial_lower = (serial or "").lower()
            best = None
            best_score = 0
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                href = a["href"].lower()
                if any(k in href for k in ["/psx/", "/playstation/", "-psx-", "-ps1-", "playstation-1", "ps1-roms", "psx-roms", "/sony-playstation", "/sony_psx", "/roms/playstation"]):
                    score = sum(1 for w in name_words if w in text)
                    if serial_lower in text:
                        score += 2
                    if score > best_score:
                        best_score = score
                        best = (a["href"], text)
            if best and best_score >= max(1, len(name_words) // 2):
                href, text = best
                url = href if href.startswith("http") else urllib.parse.urljoin(search_url, href)
                return ("page_url", url), f"{site_key}: {text[:60]}"
            return None, f"{site_key}: sem resultados"
        except Exception as e:
            return None, f"{site_key}: erro {e}"

    # ============================================================
    # SITES DESCOBERTOS PELO SUBAGENTE _web_discovery_subagent.py
    # ============================================================

    def search_classicreload(self, query, serial, name):
        if not name:
            return None, "classicreload: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        return self._generic_page_search("classicreload", f"https://www.classicreload.com/?s={quote_plus(short_name)}", short_name, serial)

    def search_classicgamezone(self, query, serial, name):
        if not name:
            return None, "classicgamezone: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        return self._generic_page_search("classicgamezone", f"https://classicgamezone.com/?s={quote_plus(short_name)}", short_name, serial)

    def search_romulation_org(self, query, serial, name):
        if not name:
            return None, "romulation_org: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        return self._generic_page_search("romulation_org", f"https://www.romulation.org/roms/PSX?q={quote_plus(short_name)}", short_name, serial)

    def search_retrogames_games(self, query, serial, name):
        if not name:
            return None, "retrogames_games: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        return self._generic_page_search("retrogames_games", f"https://retrogames.games/?s={quote_plus(short_name)}", short_name, serial)

    def search_retrogames_cc(self, query, serial, name):
        if not name:
            return None, "retrogames_cc: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        return self._generic_page_search("retrogames_cc", f"https://retrogames.cc/?s={quote_plus(short_name)}", short_name, serial)

    def search_playretrogames(self, query, serial, name):
        if not name:
            return None, "playretrogames: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        return self._generic_page_search("playretrogames", f"https://playretrogames.com/?s={quote_plus(short_name)}", short_name, serial)

    def search_playretrogames_online(self, query, serial, name):
        if not name:
            return None, "playretrogames_online: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        return self._generic_page_search("playretrogames_online", f"https://playretrogames.online/?s={quote_plus(short_name)}", short_name, serial)

    def search_oldiesnest(self, query, serial, name):
        if not name:
            return None, "oldiesnest: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        return self._generic_page_search("oldiesnest", f"https://oldiesnest.com/?s={quote_plus(short_name)}", short_name, serial)

    def search_retrogametalk(self, query, serial, name):
        if not name:
            return None, "retrogametalk: sem nome"
        short_name = re.sub(r"\(.*?\)", "", name).strip()
        return self._generic_page_search("retrogametalk", f"https://retrogametalk.com/?s={quote_plus(short_name)}", short_name, serial)

    # ============================================================
    # NOVOS SITES — ROMSBASE, HEXROM, CONSOLEROMS, ROMULATION
    # ============================================================

    def search_romsbase(self, query, serial, name):
        """Busca no RomsBase (romsbase.com) — sem anti-bot, URL direta de download.
        Search: GET https://www.romsbase.com/roms/playstation?q={name}
        Game links: href="/rom/playstation/{slug}/{id}"
        Download: https://www.romsbase.com/fetch.php?id={id}
        NOTA: As paginas de jogo NAO contem o serial. O slug tem sufixo de regiao
        (-us, -eu, -jp). Usamos o prefixo do serial (SCUS/SLUS=us, SCES/SLES=eu,
        SLPS/SCPS=jp) para matching de regiao + name match na pagina.
        """
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }
        if not serial:
            return None, "romsbase: sem serial"
        try:
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            search_url = f"https://www.romsbase.com/roms/playstation?q={quote_plus(short_name)}"
            r = requests.get(search_url, headers=req_headers, timeout=15)
            if r.status_code != 200:
                return None, f"romsbase: HTTP {r.status_code}"
            # Find game links with IDs: href="/rom/playstation/{slug}/{id}"
            links = re.findall(r'href="/rom/playstation/([^/]+)/(\d+)"', r.text)
            if not links:
                return None, "romsbase: no results"
            # Deduplicate
            seen = set()
            unique_links = []
            for slug, rom_id in links:
                key = (slug, rom_id)
                if key not in seen:
                    seen.add(key)
                    unique_links.append((slug, rom_id))
            # Determinar regiao alvo a partir do prefixo do serial
            serial_upper = serial.upper().replace("-", "").replace("_", "")
            region = None
            if serial_upper.startswith(("SCUS", "SLUS")):
                region = "us"
            elif serial_upper.startswith(("SCES", "SLES")):
                region = "eu"
            elif serial_upper.startswith(("SLPS", "SLPM", "SCPS", "SLPS")):
                region = "jp"
            name_lower = short_name.lower()
            # Primeira passada: name match + regiao correta no slug
            for slug, rom_id in unique_links[:10]:
                if region and slug.lower().endswith(f"-{region}"):
                    game_url = f"https://www.romsbase.com/rom/playstation/{slug}/{rom_id}"
                    r2 = requests.get(game_url, headers=req_headers, timeout=15)
                    if r2.status_code == 200 and name_lower in r2.text.lower():
                        # Ir direto para fetch.php (evita o timer de countdown na /download/{id})
                        dl_url = f"https://www.romsbase.com/fetch.php?id={rom_id}"
                        return ("direct_url", dl_url), f"romsbase: {slug}"
            # Segunda passada: name match apenas (fallback sem match de regiao)
            for slug, rom_id in unique_links[:10]:
                game_url = f"https://www.romsbase.com/rom/playstation/{slug}/{rom_id}"
                r2 = requests.get(game_url, headers=req_headers, timeout=15)
                if r2.status_code == 200 and name_lower in r2.text.lower():
                    dl_url = f"https://www.romsbase.com/fetch.php?id={rom_id}"
                    return ("direct_url", dl_url), f"romsbase: {slug}"
            return None, "romsbase: serial not matched"
        except Exception as e:
            return None, f"romsbase: erro {e}"

    def search_hexrom(self, query, serial, name):
        """Busca no HexROM (hexrom.com) — usa page_url para navegacao virtual.
        Search: GET https://hexrom.com/roms/playstation/?s={name}
        Game links: href="https://hexrom.com/{slug}/"
        Download page: https://hexrom.com/{slug}/download/
        Direct URL: https://s1.hexrom.com/rom/ps1/{filename}.zip
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not serial:
            return None, "hexrom: sem serial"
        try:
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            search_url = f"https://hexrom.com/roms/playstation/?s={quote_plus(short_name)}"
            r = requests.get(search_url, headers=req_headers, timeout=15)
            if r.status_code != 200:
                return None, f"hexrom: HTTP {r.status_code}"
            # Find game links: href="https://hexrom.com/{slug}/"
            links = re.findall(r'href="https://hexrom\.com/([^/]+)/"', r.text)
            # Filter out non-game links (nav, category, system pages)
            game_links = [l for l in links if not l.startswith((
                "roms", "rom-category", "category", "emulators", "bios",
                "page", "tag", "author", "about", "contact", "privacy",
                "dmca", "wp-", "search", "sitemap"))]
            if not game_links:
                return None, "hexrom: no results"
            for slug in game_links[:10]:
                # Match by serial in slug OR serial in game page
                slug_has_serial = serial.lower().replace("-", "") in slug.lower().replace("-", "")
                if not slug_has_serial:
                    # Visit game page to confirm serial
                    game_page = f"https://hexrom.com/{slug}/"
                    r3 = requests.get(game_page, headers=req_headers, timeout=15)
                    if r3.status_code != 200 or serial.lower() not in r3.text.lower():
                        continue
                # Visit download page to find direct file URL
                dl_page_url = f"https://hexrom.com/{slug}/download/"
                r2 = requests.get(dl_page_url, headers=req_headers, timeout=15)
                if r2.status_code == 200:
                    file_urls = re.findall(
                        r'(https://s\d+\.hexrom\.com/rom/ps1/[^"\']+\.zip)',
                        r2.text)
                    if file_urls:
                        return ("direct_url", file_urls[0]), f"hexrom: {slug}"
            return None, "hexrom: serial not matched"
        except Exception as e:
            return None, f"hexrom: erro {e}"

    def search_consoleroms(self, query, serial, name):
        """Busca no ConsoleRoms (consoleroms.com).
        Search: GET https://www.consoleroms.com/roms/psx?q={name}
        Game links: href="/roms/psx/{slug}"
        Download page: https://www.consoleroms.com/roms/psx/{slug}/download
        Direct URL: https://downloads.consoleroms.com/roms/{filename}.rar
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not serial:
            return None, "consoleroms: sem serial"
        try:
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            search_url = f"https://www.consoleroms.com/roms/psx?q={quote_plus(short_name)}"
            r = requests.get(search_url, headers=req_headers, timeout=15)
            if r.status_code != 200:
                return None, f"consoleroms: HTTP {r.status_code}"
            # Find game links: href="/roms/psx/{slug}"
            links = re.findall(r'href="/roms/psx/([^/"]+)"', r.text)
            if not links:
                return None, "consoleroms: no results"
            # Deduplicate
            seen = set()
            unique_links = []
            for slug in links:
                if slug not in seen:
                    seen.add(slug)
                    unique_links.append(slug)
            for slug in unique_links[:10]:
                # Visit download page directly — it contains the serial AND the file URL
                dl_page_url = f"https://www.consoleroms.com/roms/psx/{slug}/download"
                r3 = requests.get(dl_page_url, headers=req_headers, timeout=15)
                if r3.status_code == 200 and serial.lower() in r3.text.lower():
                    file_urls = re.findall(
                        r'(https://downloads\.consoleroms\.com/roms/[^"\']+\.(?:rar|zip|7z))',
                        r3.text)
                    if file_urls:
                        return ("direct_url", file_urls[0]), f"consoleroms: {slug}"
            return None, "consoleroms: serial not matched"
        except Exception as e:
            return None, f"consoleroms: erro {e}"

    def search_romulation(self, query, serial, name):
        """Busca no Romulation (romulation.org) — tem Cloudflare, pode precisar retries.
        Tem ROMs JP tambem.
        Search: GET https://www.romulation.org/roms/PSX?q={name}
        Game links: href="/rom/PSX/{slug}"
        Download link: /roms/newdownload/guest/{id}/{base64_token}
        Direct URL: https://pluto.romulation.net/files/guest/{token}/
        """
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if not serial:
            return None, "romulation: sem serial"
        try:
            short_name = re.sub(r"\(.*?\)", "", name).strip()
            short_name = re.sub(r"\[.*?\]", "", short_name).strip()
            search_url = f"https://www.romulation.org/roms/PSX?q={quote_plus(short_name)}"
            # Cloudflare: retry 3 vezes
            r = None
            for attempt in range(3):
                try:
                    r = requests.get(search_url, headers=req_headers, timeout=15)
                    if r.status_code == 200:
                        break
                    if r.status_code in (403, 503) and attempt < 2:
                        time.sleep(3)
                        continue
                    return None, f"romulation: HTTP {r.status_code}"
                except Exception:
                    if attempt < 2:
                        time.sleep(3)
                        continue
                    return None, "romulation: connection error"
            if r is None or r.status_code != 200:
                return None, "romulation: search failed"
            # Find game links: href="/rom/PSX/{slug}"
            links = re.findall(r'href="/rom/PSX/([^/"]+)"', r.text)
            if not links:
                return None, "romulation: no results"
            # Deduplicate
            seen = set()
            unique_links = []
            for slug in links:
                if slug not in seen:
                    seen.add(slug)
                    unique_links.append(slug)
            # Romulation returns many results; the target may be far down the list.
            # Also, serial is NOT on the game page but IS in the slug.
            serial_clean = serial.lower().replace("-", "")
            for slug in unique_links[:25]:
                # Match by serial in slug (preferred) or serial in page text
                slug_has_serial = serial_clean in slug.lower().replace("-", "")
                game_url = f"https://www.romulation.org/rom/PSX/{slug}"
                r2 = None
                for attempt in range(3):
                    try:
                        r2 = requests.get(game_url, headers=req_headers, timeout=15)
                        if r2.status_code == 200:
                            break
                        if r2.status_code in (403, 503) and attempt < 2:
                            time.sleep(3)
                            continue
                        break
                    except Exception:
                        if attempt < 2:
                            time.sleep(3)
                            continue
                        break
                if r2 is None or r2.status_code != 200:
                    continue
                if not slug_has_serial and serial.lower() not in r2.text.lower():
                    continue
                # Find download link: /roms/newdownload/guest/{id}/{base64_token}
                dl_matches = re.findall(
                    r'/roms/newdownload/guest/(\d+)/([A-Za-z0-9+/=_-]+)',
                    r2.text)
                if not dl_matches:
                    continue
                for dl_id, token in dl_matches[:2]:
                    dl_page_url = f"https://www.romulation.org/roms/newdownload/guest/{dl_id}/{token}"
                    r3 = None
                    for attempt in range(3):
                        try:
                            r3 = requests.get(dl_page_url, headers=req_headers, timeout=15)
                            if r3.status_code == 200:
                                break
                            if r3.status_code in (403, 503) and attempt < 2:
                                time.sleep(3)
                                continue
                            break
                        except Exception:
                            if attempt < 2:
                                time.sleep(3)
                                continue
                            break
                    if r3 is None or r3.status_code != 200:
                        continue
                    # Find direct file URL: https://pluto.romulation.net/files/guest/{token}/
                    file_urls = re.findall(
                        r'(https://pluto\.romulation\.net/files/guest/[^"\']+)',
                        r3.text)
                    if file_urls:
                        return ("direct_url", file_urls[0]), f"romulation: {slug}"
            return None, "romulation: serial not matched"
        except Exception as e:
            return None, f"romulation: erro {e}"


def buffer_load():
    """Carrega o buffer compartilhado do arquivo."""
    return load_json(BUFFER_PATH, {})


def buffer_save(data):
    """Salva o buffer compartilhado no arquivo."""
    save_json(BUFFER_PATH, data)


def buffer_add(serial, result_type, url, site, detail):
    """Adiciona uma URL encontrada ao buffer compartilhado."""
    fl = file_lock()
    try:
        data = buffer_load()
        data[serial] = {"type": result_type, "url": url, "site": site, "detail": detail}
        buffer_save(data)
    finally:
        file_unlock(fl)


def buffer_pop_ready():
    """Pega uma URL pronta do buffer compartilhado, priorizando sites
    com menos downloads ativos (balanceamento de carga)."""
    fl = file_lock()
    try:
        data = buffer_load()
        # Coletar todas as entradas prontas
        ready = []
        for serial, entry in data.items():
            if entry.get("type") != "searching" and entry.get("url"):
                ready.append((serial, entry))
        if not ready:
            return None, None
        # Contar downloads ativos por site
        active = get_active_downloads_per_site()
        # Ordenar por (num_downloads_ativos_no_site, ordem_de_insercao)
        # Mantem FIFO entre sites com mesma carga
        items = list(data.items())
        ready_with_idx = []
        for serial, entry in ready:
            site = entry.get("site", "")
            load = active.get(site, 0)
            idx = next(i for i, (s, _) in enumerate(items) if s == serial)
            ready_with_idx.append((load, idx, serial, entry))
        ready_with_idx.sort(key=lambda x: (x[0], x[1]))
        # Pegar o primeiro (menor carga)
        _, _, serial, entry = ready_with_idx[0]
        del data[serial]
        buffer_save(data)
        return serial, entry
    finally:
        file_unlock(fl)


def buffer_mark_searching(serial):
    """Marca um serial como 'buscando' no buffer."""
    fl = file_lock()
    try:
        data = buffer_load()
        data[serial] = {"type": "searching", "url": None, "site": None, "detail": None}
        buffer_save(data)
    finally:
        file_unlock(fl)


def buffer_remove(serial):
    """Remove um serial do buffer."""
    fl = file_lock()
    try:
        data = buffer_load()
        data.pop(serial, None)
        buffer_save(data)
    finally:
        file_unlock(fl)


def buffer_count_ready():
    """Conta quantas URLs prontas ha no buffer."""
    data = buffer_load()
    return sum(1 for v in data.values() if v.get("type") != "searching" and v.get("url"))


def buffer_count_total():
    """Conta total de entradas no buffer."""
    return len(buffer_load())


def get_active_downloads_per_site():
    """Conta quantos downloads estao ativos por site lendo queue.json.
    Retorna dict {site_key: count}. Sites sem downloads ativos ficam com 0.
    """
    try:
        data = load_json(QUEUE_PATH, {"in_progress": {}})
        in_progress = data.get("in_progress", {})
        counts = {}
        for serial, info in in_progress.items():
            site = info.get("_current_site", "")
            if site:
                counts[site] = counts.get(site, 0) + 1
        return counts
    except Exception:
        return {}


def get_balanced_site_order(all_sites, base_order=None):
    """Retorna lista de sites ordenada por menor numero de downloads ativos.
    Sites com mesmo numero de downloads ativos mantem ordem original (round-robin).
    Sites nao presentes nos downloads ativos ficam primeiro (count=0).
    """
    if base_order is None:
        base_order = all_sites
    active = get_active_downloads_per_site()
    # Ordenar por (num_downloads_ativos, posicao_original) — estavel
    indexed = [(active.get(s, 0), i, s) for i, s in enumerate(base_order)]
    indexed.sort(key=lambda x: (x[0], x[1]))
    return [s for _, _, s in indexed]


def misses_load():
    """Carrega lista de seriais ja buscados sem sucesso."""
    return set(load_json(MISSES_PATH, []))


def misses_add(serial):
    """Adiciona serial a lista de misses."""
    fl = file_lock()
    try:
        data = list(load_json(MISSES_PATH, []))
        if serial not in data:
            data.append(serial)
            save_json(MISSES_PATH, data)
    finally:
        file_unlock(fl)


def misses_contains(serial):
    """Verifica se serial esta na lista de misses."""
    return serial in misses_load()


def presearch_worker(navigator=None, worker_id=99, max_items=None):
    """Searcher dedicado: pre-busca URLs para os proximos itens da fila.
    Usa apenas requests (sem Playwright) para evitar conflitos de asyncio.
    Roda em background, enchendo o buffer para que os workers possam baixar direto.
    Se max_items for definido, para apos buscar N itens.
    """
    wlog = logging.getLogger(f"presearch-{worker_id}")
    wlog.info("Pre-searcher iniciado (requests-only)")
    items_searched = 0
    while True:
        try:
            if max_items is not None and items_searched >= max_items:
                wlog.info(f"Pre-searcher finalizado ({items_searched} itens buscados)")
                break
            action, paused = check_control()
            if action == "stop":
                break
            if action == "pause" or paused:
                time.sleep(2)
                continue

            # Verificar se o buffer precisa de mais itens
            with PRESEARCH_LOCK:
                buffer_size = len(PRESEARCH_BUFFER)
                # Limpar entradas "searching" antigas (mais de 60s)
                now = time.time()
                to_remove = []
                for serial, entry in PRESEARCH_BUFFER.items():
                    if isinstance(entry, tuple) and entry[0] == "searching":
                        # entry = ("searching", timestamp, None, None)
                        ts = entry[1] if len(entry) > 1 and isinstance(entry[1], (int, float)) else 0
                        if now - ts > 60:
                            to_remove.append(serial)
                    elif isinstance(entry, tuple) and entry[0] == "failed":
                        # entry = ("failed", expire_timestamp, None, None)
                        expire = entry[1] if len(entry) > 1 and isinstance(entry[1], (int, float)) else 0
                        if now > expire:
                            to_remove.append(serial)
                for s in to_remove:
                    PRESEARCH_BUFFER.pop(s, None)
                searching_count = sum(1 for v in PRESEARCH_BUFFER.values() if v[0] == "searching")

            if buffer_size >= PRESEARCH_MAX:
                time.sleep(0.5)
                continue

            # Pegar proximo item da fila que ainda nao esta no buffer nem em progresso
            data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}, "completed": {}})
            queue = data.get("queue", [])
            in_progress = data.get("in_progress", {})
            completed = data.get("completed", {})

            item = None
            for q_item in queue:
                serial, norm_item = normalize_queue_item(q_item)
                if not serial:
                    continue
                with PRESEARCH_LOCK:
                    in_buffer = serial in PRESEARCH_BUFFER
                if not in_buffer and serial not in in_progress and serial not in completed:
                    item = norm_item if isinstance(q_item, str) else q_item
                    break

            if item is None:
                time.sleep(1)
                continue

            # Marcar como em busca no buffer (para evitar duplicacao)
            with PRESEARCH_LOCK:
                PRESEARCH_BUFFER[item["serial"]] = ("searching", time.time(), None, None)
            save_presearch_buffer()

            items_searched += 1

            # Buscar usando apenas sites que funcionam com requests (sem Playwright)
            serial = item["serial"]
            name = item["name"]
            short_query = re.sub(r"\(.*?\)", "", name).strip()
            short_query = re.sub(r"\[.*?\]", "", short_query).strip()
            sites = load_sites()
            blacklist = load_blacklist()

            found_result = None
            found_detail = ""
            found_site = ""
            is_jp = serial.startswith(("SLPS", "SLPM", "SCPS", "SLKA"))
            search_t0 = time.time()
            SITE_TIMEOUT = 15  # max 15s por site
            MAX_SEARCH_TIME = 30 if is_jp else 45  # JP: menos sites, menos tempo

            # Round-robin: cada searcher pega uma ordem diferente de sites
            # archive_org fica por ultimo na rotacao (prioridade base alta, mas rotaciona)
            all_presearch_sites = ["coolrom", "blueroms", "romsretro", "romsfun", "vimm", "romspedia", "retroiso", "retromania", "romsdl", "retrostic", "cdromance", "romsgames", "romhustler", "archive_org", "emuparadise", "romspack", "totalroms", "romspure", "retrobit", "roms2000", "classicgames", "freeroms", "classicreload", "classicgamezone", "romulation_org", "retrogames_games", "retrogames_cc", "playretrogames", "playretrogames_online", "oldiesnest", "retrogametalk", "hexrom", "consoleroms", "romulation"]
            if is_jp:
                # JP: archive_org_jp e archive_org primeiro (indice JP por nome = instantaneo)
                base_jp_sites = ["archive_org_jp", "archive_org", "blueroms", "romsretro", "coolrom", "retrostic_jp", "psxdatacenter_jp", "romulation", "hexrom", "consoleroms"]
                all_presearch_sites = [s for s in base_jp_sites if s in sites and sites[s].get("enabled")]
                if not all_presearch_sites:
                    all_presearch_sites = ["archive_org_jp", "archive_org", "coolrom"]
            # Rotacionar ordem (round-robin global entre threads)
            presearch_sites = get_rotated_site_order(all_presearch_sites, sites)

            for site_key in presearch_sites:
                # Limite de tempo total por item
                if time.time() - search_t0 > MAX_SEARCH_TIME:
                    wlog.debug(f"Timeout total para {serial} apos {MAX_SEARCH_TIME}s")
                    break

                site = sites.get(site_key)
                if not site or not site.get("enabled"):
                    continue
                if site_key in blacklist.get("sites", []):
                    continue

                try:
                    result = None
                    detail = ""
                    # Criar instancia fake para chamar metodos de classe
                    class FakeNav:
                        pass
                    fake = FakeNav()
                    fake.search_coolrom = SiteNavigator.search_coolrom.__get__(fake)
                    fake.search_retrostic = SiteNavigator.search_retrostic.__get__(fake)
                    fake.search_romsdl = SiteNavigator.search_romsdl.__get__(fake)
                    fake.search_archive_org = SiteNavigator.search_archive_org.__get__(fake)
                    fake.search_romspedia = SiteNavigator.search_romspedia.__get__(fake)
                    fake.search_romsgames = SiteNavigator.search_romsgames.__get__(fake)
                    fake.search_retromania = SiteNavigator.search_retromania.__get__(fake)
                    fake.search_romsfun = SiteNavigator.search_romsfun.__get__(fake)
                    fake.search_romhustler = SiteNavigator.search_romhustler.__get__(fake)
                    fake.search_vimm_cache = SiteNavigator.search_vimm_cache.__get__(fake)
                    fake.search_retroiso = SiteNavigator.search_retroiso.__get__(fake)
                    fake.search_psxdatacenter_jp = SiteNavigator.search_psxdatacenter_jp.__get__(fake)
                    fake.search_retrostic_jp = SiteNavigator.search_retrostic_jp.__get__(fake)
                    fake.search_archive_org_jp = SiteNavigator.search_archive_org_jp.__get__(fake)
                    fake.search_romsbase = SiteNavigator.search_romsbase.__get__(fake)
                    fake.search_hexrom = SiteNavigator.search_hexrom.__get__(fake)
                    fake.search_consoleroms = SiteNavigator.search_consoleroms.__get__(fake)
                    fake.search_romulation = SiteNavigator.search_romulation.__get__(fake)
                    fake.search_myrient = SiteNavigator.search_myrient.__get__(fake)
                    fake.search_emuparadise = SiteNavigator.search_emuparadise.__get__(fake)
                    fake.search_romspack = SiteNavigator.search_romspack.__get__(fake)
                    fake.search_totalroms = SiteNavigator.search_totalroms.__get__(fake)
                    fake.search_romspure = SiteNavigator.search_romspure.__get__(fake)
                    fake.search_roms2000 = SiteNavigator.search_roms2000.__get__(fake)
                    fake.search_classicgames = SiteNavigator.search_classicgames.__get__(fake)
                    fake.search_retrobit = SiteNavigator.search_retrobit.__get__(fake)
                    fake.search_freeroms = SiteNavigator.search_freeroms.__get__(fake)
                    fake.search_classicreload = SiteNavigator.search_classicreload.__get__(fake)
                    fake.search_classicgamezone = SiteNavigator.search_classicgamezone.__get__(fake)
                    fake.search_romulation_org = SiteNavigator.search_romulation_org.__get__(fake)
                    fake.search_retrogames_games = SiteNavigator.search_retrogames_games.__get__(fake)
                    fake.search_retrogames_cc = SiteNavigator.search_retrogames_cc.__get__(fake)
                    fake.search_playretrogames = SiteNavigator.search_playretrogames.__get__(fake)
                    fake.search_playretrogames_online = SiteNavigator.search_playretrogames_online.__get__(fake)
                    fake.search_oldiesnest = SiteNavigator.search_oldiesnest.__get__(fake)
                    fake.search_retrogametalk = SiteNavigator.search_retrogametalk.__get__(fake)

                    # Mapear site_key -> funcao de busca
                    search_funcs = {
                        "coolrom": lambda: fake.search_coolrom(short_query, serial, name),
                        "blueroms": lambda: fake.search_blueroms(short_query, serial, name),
                        "romsretro": lambda: fake.search_romsretro(short_query, serial, name),
                        "retrostic": lambda: fake.search_retrostic(short_query, serial, name),
                        "romsdl": lambda: fake.search_romsdl(short_query, serial, name),
                        "archive_org": lambda: fake.search_archive_org(short_query, serial, name),
                        "archive_org_jp": lambda: fake.search_archive_org_jp(short_query, serial, name),
                        "psxdatacenter_jp": lambda: fake.search_psxdatacenter_jp(short_query, serial, name),
                        "retrostic_jp": lambda: fake.search_retrostic_jp(short_query, serial, name),
                        "romsfun": lambda: fake.search_romsfun(short_query, serial, name),
                        "vimm": lambda: fake.search_vimm_cache(serial, name),
                        "romspedia": lambda: fake.search_romspedia(short_query, serial, name),
                        "retroiso": lambda: fake.search_retroiso(short_query, serial, name),
                        "retromania": lambda: fake.search_retromania(short_query, serial, name),
                        "romsgames": lambda: fake.search_romsgames(short_query, serial, name),
                        "romhustler": lambda: fake.search_romhustler(short_query, serial, name),
                        "romsbase": lambda: fake.search_romsbase(short_query, serial, name),
                        "hexrom": lambda: fake.search_hexrom(short_query, serial, name),
                        "consoleroms": lambda: fake.search_consoleroms(short_query, serial, name),
                        "romulation": lambda: fake.search_romulation(short_query, serial, name),
                        "emuparadise": lambda: fake.search_emuparadise(short_query, serial, name),
                        "romspack": lambda: fake.search_romspack(short_query, serial, name),
                        "totalroms": lambda: fake.search_totalroms(short_query, serial, name),
                        "romspure": lambda: fake.search_romspure(short_query, serial, name),
                        "roms2000": lambda: fake.search_roms2000(short_query, serial, name),
                        "classicgames": lambda: fake.search_classicgames(short_query, serial, name),
                        "retrobit": lambda: fake.search_retrobit(short_query, serial, name),
                        "freeroms": lambda: fake.search_freeroms(short_query, serial, name),
                        "classicreload": lambda: fake.search_classicreload(short_query, serial, name),
                        "classicgamezone": lambda: fake.search_classicgamezone(short_query, serial, name),
                        "romulation_org": lambda: fake.search_romulation_org(short_query, serial, name),
                        "retrogames_games": lambda: fake.search_retrogames_games(short_query, serial, name),
                        "retrogames_cc": lambda: fake.search_retrogames_cc(short_query, serial, name),
                        "playretrogames": lambda: fake.search_playretrogames(short_query, serial, name),
                        "playretrogames_online": lambda: fake.search_playretrogames_online(short_query, serial, name),
                        "oldiesnest": lambda: fake.search_oldiesnest(short_query, serial, name),
                        "retrogametalk": lambda: fake.search_retrogametalk(short_query, serial, name),
                        "google": lambda: fake.search_google(short_query, serial, name),
                    }

                    search_fn = search_funcs.get(site_key)
                    if not search_fn:
                        continue

                    # Chamada direta com try/except (timeout ja no requests.get)
                    site_t0 = time.time()
                    wlog.info(f"Buscando {serial} em {site_key}...")
                    try:
                        result, detail = search_fn()
                    except Exception as e:
                        wlog.debug(f"Erro em {site_key} para {serial}: {e}")
                        result, detail = None, str(e)
                    site_dt = time.time() - site_t0
                    wlog.info(f"  {site_key} para {serial}: {'OK' if result else 'fail'} em {site_dt:.1f}s")

                    if result:
                        found_result = result
                        found_detail = detail
                        found_site = site_key
                        break
                except Exception as e:
                    wlog.debug(f"Erro em {site_key} para {serial}: {e}")
                    continue

            # Salvar no buffer
            with PRESEARCH_LOCK:
                if found_result:
                    PRESEARCH_BUFFER[serial] = (found_result[0], found_result[1], found_site, found_detail)
                    wlog.info(f"Pre-search OK: {serial} via {found_site}")
                else:
                    # Marcar como falho por 5min para nao re-tentar imediatamente
                    PRESEARCH_BUFFER[serial] = ("failed", time.time() + 300, None, None)
                    wlog.debug(f"Pre-search falhou para {serial} — re-tentar em 5min")
            save_presearch_buffer()

        except Exception as e:
            wlog.error(f"Erro no pre-searcher: {e}")
            time.sleep(2)

    wlog.info("Pre-searcher finalizado")


def search_item_for_downloader(serial, name, sites, blacklist):
    """Busca URL on-the-fly para um item do downloader.
    Tenta todos os sites em ordem round-robin e retorna (result_type, url, site_key, detail)
    ou (None, None, None, None) se falhar. Reserva o site com acquire_site.
    """
    if not sites:
        log.info(f"[search_item_for_downloader] {serial}: nenhum site configurado")
        return None, None, None, None

    short_query = re.sub(r"\(.*?\)", "", name).strip()
    short_query = re.sub(r"\[.*?\]", "", short_query).strip()

    is_jp = serial.startswith(("SLPS", "SLPM", "SCPS", "SLKA"))

    is_homebrew = serial.startswith("HBREW") or serial.startswith("HOMEBREW")

    # ===== Dinamico: usar TODOS os sites ativos do sites.json =====
    # Priorizar sites por priority (menor = mais prioritario)
    all_enabled = sorted(
        [k for k, v in sites.items() if v.get("enabled") and k not in blacklist.get("sites", [])],
        key=lambda k: sites[k].get("priority", 99)
    )

    if is_homebrew:
        # Homebrew: homebrew primeiro, depois todos os outros
        priority_sites = ["homebrew", "archive_org", "google"]
        all_sites = [s for s in priority_sites if s in all_enabled]
        all_sites += [s for s in all_enabled if s not in all_sites]
        if not all_sites:
            all_sites = ["homebrew"]
    elif is_jp:
        # JP: apenas sites com cobertura JP — nao desperdicar tempo em sites ocidentais
        jp_sites = ["archive_org_jp", "archive_org", "coolrom", "romulation", "psxdatacenter_jp", "retrostic_jp", "retroiso", "hexrom", "google", "homebrew"]
        all_sites = [s for s in jp_sites if s in all_enabled]
        if not all_sites:
            all_sites = ["archive_org_jp", "archive_org", "coolrom"]
    else:
        # USA/EU: apenas sites mais produtivos (nao tentar todos os 24+)
        us_eu_sites = ["archive_org", "coolrom", "romulation", "retrostic", "retroiso", "romsretro",
                       "romspedia", "hexrom", "consoleroms", "romsgames", "retromania", "romsdl",
                       "romspure", "oldiesnest", "google", "homebrew"]
        all_sites = [s for s in us_eu_sites if s in all_enabled]
        if not all_sites:
            all_sites = ["archive_org", "coolrom", "romulation"]

    site_order = get_rotated_site_order(all_sites, sites)

    log.info(f"[search_item_for_downloader] {serial} ({name[:60]}): iniciando busca em {site_order}")

    # Instancia fake para chamar metodos de classe do SiteNavigator sem Playwright
    class FakeNav:
        pass
    fake = FakeNav()
    fake.search_coolrom = SiteNavigator.search_coolrom.__get__(fake)
    fake.search_homebrew = SiteNavigator.search_homebrew.__get__(fake)
    fake.search_archive_org = SiteNavigator.search_archive_org.__get__(fake)
    fake.search_archive_org_jp = SiteNavigator.search_archive_org_jp.__get__(fake)
    fake.search_retrostic = SiteNavigator.search_retrostic.__get__(fake)
    fake.search_retrostic_jp = SiteNavigator.search_retrostic_jp.__get__(fake)
    fake.search_romsdl = SiteNavigator.search_romsdl.__get__(fake)
    fake.search_romsfun = SiteNavigator.search_romsfun.__get__(fake)
    fake.search_vimm_cache = SiteNavigator.search_vimm_cache.__get__(fake)
    fake.search_romspedia = SiteNavigator.search_romspedia.__get__(fake)
    fake.search_retroiso = SiteNavigator.search_retroiso.__get__(fake)
    fake.search_retromania = SiteNavigator.search_retromania.__get__(fake)
    fake.search_romsgames = SiteNavigator.search_romsgames.__get__(fake)
    fake.search_romhustler = SiteNavigator.search_romhustler.__get__(fake)
    fake.search_psxdatacenter_jp = SiteNavigator.search_psxdatacenter_jp.__get__(fake)
    fake.search_cdromance = SiteNavigator.search_cdromance.__get__(fake)
    fake.search_romsbase = SiteNavigator.search_romsbase.__get__(fake)
    fake.search_hexrom = SiteNavigator.search_hexrom.__get__(fake)
    fake.search_consoleroms = SiteNavigator.search_consoleroms.__get__(fake)
    fake.search_romulation = SiteNavigator.search_romulation.__get__(fake)
    fake.search_myrient = SiteNavigator.search_myrient.__get__(fake)
    fake.search_emuparadise = SiteNavigator.search_emuparadise.__get__(fake)
    fake.search_romspack = SiteNavigator.search_romspack.__get__(fake)
    fake.search_totalroms = SiteNavigator.search_totalroms.__get__(fake)
    fake.search_romspure = SiteNavigator.search_romspure.__get__(fake)
    fake.search_roms2000 = SiteNavigator.search_roms2000.__get__(fake)
    fake.search_classicgames = SiteNavigator.search_classicgames.__get__(fake)
    fake.search_retrobit = SiteNavigator.search_retrobit.__get__(fake)
    fake.search_freeroms = SiteNavigator.search_freeroms.__get__(fake)
    fake.search_classicreload = SiteNavigator.search_classicreload.__get__(fake)
    fake.search_classicgamezone = SiteNavigator.search_classicgamezone.__get__(fake)
    fake.search_romulation_org = SiteNavigator.search_romulation_org.__get__(fake)
    fake.search_retrogames_games = SiteNavigator.search_retrogames_games.__get__(fake)
    fake.search_retrogames_cc = SiteNavigator.search_retrogames_cc.__get__(fake)
    fake.search_playretrogames = SiteNavigator.search_playretrogames.__get__(fake)
    fake.search_playretrogames_online = SiteNavigator.search_playretrogames_online.__get__(fake)
    fake.search_oldiesnest = SiteNavigator.search_oldiesnest.__get__(fake)
    fake.search_retrogametalk = SiteNavigator.search_retrogametalk.__get__(fake)
    fake.search_google = SiteNavigator.search_google.__get__(fake)

    search_funcs = {
        "homebrew": lambda: fake.search_homebrew(name, serial, name),
        "coolrom": lambda: fake.search_coolrom(short_query, serial, name),
        "blueroms": lambda: fake.search_blueroms(short_query, serial, name),
        "romsretro": lambda: fake.search_romsretro(short_query, serial, name),
        "archive_org": lambda: fake.search_archive_org(short_query, serial, name),
        "archive_org_jp": lambda: fake.search_archive_org_jp(short_query, serial, name),
        "retrostic": lambda: fake.search_retrostic(short_query, serial, name),
        "retrostic_jp": lambda: fake.search_retrostic_jp(short_query, serial, name),
        "romsdl": lambda: fake.search_romsdl(short_query, serial, name),
        "romsfun": lambda: fake.search_romsfun(short_query, serial, name),
        "vimm": lambda: fake.search_vimm_cache(serial, name),
        "romspedia": lambda: fake.search_romspedia(short_query, serial, name),
        "retroiso": lambda: fake.search_retroiso(short_query, serial, name),
        "retromania": lambda: fake.search_retromania(short_query, serial, name),
        "romsgames": lambda: fake.search_romsgames(short_query, serial, name),
        "romhustler": lambda: fake.search_romhustler(short_query, serial, name),
        "psxdatacenter_jp": lambda: fake.search_psxdatacenter_jp(short_query, serial, name),
        "cdromance": lambda: fake.search_cdromance(short_query, serial, name),
        "romsbase": lambda: fake.search_romsbase(short_query, serial, name),
        "hexrom": lambda: fake.search_hexrom(short_query, serial, name),
        "consoleroms": lambda: fake.search_consoleroms(short_query, serial, name),
        "romulation": lambda: fake.search_romulation(short_query, serial, name),
        "emuparadise": lambda: fake.search_emuparadise(short_query, serial, name),
        "romspack": lambda: fake.search_romspack(short_query, serial, name),
        "totalroms": lambda: fake.search_totalroms(short_query, serial, name),
        "romspure": lambda: fake.search_romspure(short_query, serial, name),
        "roms2000": lambda: fake.search_roms2000(short_query, serial, name),
        "classicgames": lambda: fake.search_classicgames(short_query, serial, name),
        "retrobit": lambda: fake.search_retrobit(short_query, serial, name),
        "freeroms": lambda: fake.search_freeroms(short_query, serial, name),
        "classicreload": lambda: fake.search_classicreload(short_query, serial, name),
        "classicgamezone": lambda: fake.search_classicgamezone(short_query, serial, name),
        "romulation_org": lambda: fake.search_romulation_org(short_query, serial, name),
        "retrogames_games": lambda: fake.search_retrogames_games(short_query, serial, name),
        "retrogames_cc": lambda: fake.search_retrogames_cc(short_query, serial, name),
        "playretrogames": lambda: fake.search_playretrogames(short_query, serial, name),
        "playretrogames_online": lambda: fake.search_playretrogames_online(short_query, serial, name),
        "oldiesnest": lambda: fake.search_oldiesnest(short_query, serial, name),
        "retrogametalk": lambda: fake.search_retrogametalk(short_query, serial, name),
        "google": lambda: fake.search_google(short_query, serial, name),
    }

    for site_key in site_order:
        if site_key in blacklist.get("sites", []):
            log.info(f"[search_item_for_downloader] {serial}: {site_key} na blacklist")
            continue

        search_fn = search_funcs.get(site_key)
        if not search_fn:
            log.info(f"[search_item_for_downloader] {serial}: {site_key} sem funcao de busca")
            continue

        log.info(f"Fallback search for {serial}: trying {site_key}")
        try:
            result = search_fn()
            if result and result[0]:
                result_type, url = result[0]
                detail = result[1]
                if not acquire_site(site_key, serial):
                    log.debug(f"[search_item_for_downloader] {serial}: {site_key} cheio, tentando proximo")
                    continue
                log.info(f"[search_item_for_downloader] {serial}: SUCESSO e reservado em {site_key} -> {result_type} {str(url)[:100]}")
                return result_type, url, site_key, detail
            else:
                fail_detail = result[1] if result else "sem resultado"
                log.debug(f"[search_item_for_downloader] {serial}: {site_key} falhou ({fail_detail})")
        except Exception as e:
            log.debug(f"[search_item_for_downloader] {serial}: {site_key} erro {e}")

    log.info(f"[search_item_for_downloader] {serial}: todos os sites falharam por serial — entrando no fallback por nome")

    # FALLBACK: Try by game name instead of serial
    log.info(f"[search_item_for_downloader] {serial}: serial search failed, trying by name '{name}'")
    if name and name != serial:
        # JP: tentar archive_org_jp por nome primeiro (usa indice JP por nome + colecoes JP)
        if is_jp and "archive_org_jp" in sites and sites.get("archive_org_jp", {}).get("enabled") and "archive_org_jp" not in blacklist.get("sites", []):
            try:
                log.info(f"[search_item_for_downloader] {serial}: JP name fallback -> archive_org_jp")
                result = fake.search_archive_org_jp(name, serial, name)
                if result and result[0]:
                    result_type, url = result[0]
                    detail = result[1]
                    site_key = "archive_org_jp"
                    if acquire_site(site_key, serial):
                        log.info(f"[search_item_for_downloader] {serial}: FOUND by name via {site_key}")
                        return result_type, url, site_key, detail
                    log.info(f"[search_item_for_downloader] {serial}: {site_key} cheio no fallback por nome")
                else:
                    log.info(f"[search_item_for_downloader] {serial}: archive_org_jp name fallback sem resultado ({result[1] if result else 'None'})")
            except Exception as e:
                log.warning(f"[search_item_for_downloader] {serial}: archive_org_jp name search error: {e}")

        # Try archive.org by name (pass name as query to force name-based search)
        try:
            log.info(f"[search_item_for_downloader] {serial}: name fallback -> archive_org")
            result = fake.search_archive_org(name, serial, name)
            if result and result[0]:
                result_type, url = result[0]
                detail = result[1]
                site_key = "archive_org"
                if acquire_site(site_key, serial):
                    log.info(f"[search_item_for_downloader] {serial}: FOUND by name via {site_key}")
                    return result_type, url, site_key, detail
                log.info(f"[search_item_for_downloader] {serial}: {site_key} cheio no fallback por nome")
            else:
                log.info(f"[search_item_for_downloader] {serial}: archive_org name fallback sem resultado ({result[1] if result else 'None'})")
        except Exception as e:
            log.warning(f"[search_item_for_downloader] {serial}: archive_org name search error: {e}")

        # Try coolrom fuzzy search by name (uses coolrom_index word_index)
        if "coolrom" in sites and sites["coolrom"].get("enabled") and "coolrom" not in blacklist.get("sites", []):
            try:
                result = fake.search_coolrom(name, serial, name)
                if result and result[0]:
                    result_type, url = result[0]
                    detail = result[1]
                    site_key = "coolrom"
                    if acquire_site(site_key, serial):
                        log.info(f"[search_item_for_downloader] {serial}: FOUND by name via {site_key}")
                        return result_type, url, site_key, detail
            except Exception as e:
                log.debug(f"[search_item_for_downloader] {serial}: coolrom name search error: {e}")

    # ===== FALLBACK FINAL: Bing/DuckDuckGo via HTTP (sem browser) =====
    log.info(f"[search_item_for_downloader] {serial}: fallback final -> Bing/DuckDuckGo")
    try:
        result = fake.search_google(short_query, serial, name)
        if result and result[0]:
            result_type, url = result[0]
            detail = result[1]
            site_key = "google"
            if acquire_site(site_key, serial):
                log.info(f"[search_item_for_downloader] {serial}: FOUND via Bing/DDG -> {result_type} {str(url)[:80]}")
                return result_type, url, site_key, detail
    except Exception as e:
        log.debug(f"[search_item_for_downloader] {serial}: google fallback error: {e}")

    log.info(f"[search_item_for_downloader] {serial}: todos os sites falharam (serial + name + bing/ddg)")
    return None, None, None, None


def get_presearched_url(serial):
    """Verifica se ha uma URL pre-buscada para o serial. Retorna (result_type, url, site, detail) ou None."""
    with PRESEARCH_LOCK:
        entry = PRESEARCH_BUFFER.get(serial)
        if entry and entry[0] not in ("searching", "failed") and entry[1] is not None:
            result_type, url, site, detail = PRESEARCH_BUFFER.pop(serial)
            need_save = True
        else:
            need_save = False
    if need_save:
        save_presearch_buffer()
        return result_type, url, site, detail
    return None




def build_query(item):
    if item["type"] == "homebrew":
        return f"{item['name']} psx ps1 homebrew"
    name = item["name"]
    name = re.sub(r"\(.*?\)", "", name).strip()
    name = re.sub(r"\[.*?\]", "", name).strip()
    return f"{name} {item['serial']} psx ps1"


def finalize_homebrew_path(extracted_path, serial, name):
    """Renomeia arquivo final de homebrew para conter serial e nome, garantindo dedup."""
    if not extracted_path:
        return None
    p = Path(extracted_path)
    if not p.exists():
        return extracted_path
    # Se ja contem serial no nome, nao renomeia
    if serial.replace("-", "").lower() in p.name.replace("-", "").lower():
        return p
    # Novo nome: Nome do Jogo [SERIAL].ext
    safe_name = re.sub(r'[\\/:*?"<>|]', "", name).strip()
    if not safe_name:
        safe_name = serial
    new_name = f"{safe_name} [{serial}]{p.suffix}"
    dest = p.parent / new_name
    try:
        p.rename(dest)
        return dest
    except Exception as e:
        log.debug(f"finalize_homebrew rename erro: {e}")
        return p


def process_item(item, navigator, sites, blacklist):
    serial = item["serial"]
    name = item["name"]
    short_query = re.sub(r"\(.*?\)", "", name).strip()
    short_query = re.sub(r"\[.*?\]", "", short_query).strip()

    # === Verificar pre-search buffer ===
    # Se o item ja veio como "downloading" (pre-search ready), pegar URL imediatamente
    presearched = get_presearched_url(serial)
    if not presearched and item.get("_phase") != "downloading":
        # Esperar searcher encontrar (max 5s, checando a cada 0.5s)
        # Reduzido para evitar downloaders ociosos quando o buffer esvazia
        for _ in range(10):
            time.sleep(0.5)
            presearched = get_presearched_url(serial)
            if presearched:
                break
        if not presearched:
            # Apos 5s sem URL pronta, fazer busca normal (fallback)
            log.debug(f"Sem pre-search apos 5s para {serial}, buscando normal...")
    if presearched:
        result_type, url, site_key, detail = presearched
        log.info(f"Pre-search hit: {serial} -> {site_key} ({result_type})")
        queue_update_phase(serial, "starting", site_key, f"pre-search: {detail[:80]}")
        if not acquire_site(site_key, serial):
            # Site ocupado, tentar novamente em 2s (reduzido para nao segurar workers ociosos)
            time.sleep(2)
            if not acquire_site(site_key, serial):
                log.debug(f"Site {site_key} ocupado apos espera, fazendo busca normal")
                presearched = None
        if presearched:
            try:
                if result_type == "direct_url":
                    dl_result, dl_msg = navigator.download_direct_url(url, serial)
                elif result_type == "archive_item":
                    dl_result, dl_msg = navigator.download_archive_item(url, serial, name)
                else:
                    dl_result, dl_msg = navigator.download_via_browser(url, serial)

                if dl_result:
                    # Verificar e extrair
                    verified, verify_msg = verify_download(dl_result)
                    if verified:
                        extracted = extract_rom(dl_result, PSX_DIR, serial, name)
                        if extracted:
                            try:
                                dl_result.unlink()
                            except:
                                pass
                            if item.get("type") == "homebrew":
                                extracted = finalize_homebrew_path(extracted, serial, name)
                        queue_mark_success(serial, str(extracted or dl_result), site_key)
                        log.info(f"OK: {serial} via {site_key} (pre-search) — {verify_msg}")
                        return True
                    else:
                        log.warning(f"Verify falhou (pre-search {site_key}): {verify_msg}")
                        try:
                            dl_result.unlink()
                        except:
                            pass
                else:
                    log.warning(f"Download falhou (pre-search {site_key}): {dl_msg}")
            except Exception as e:
                log.error(f"Erro pre-search download {serial}: {e}")
            finally:
                release_site(site_key, serial)
                queue_clear_progress(serial)

    site_order = get_optimized_site_order(sites, blacklist)
    if not site_order:
        site_order = [s for s in sites if sites[s].get("enabled") and s not in blacklist.get("sites", [])]

    # Se todos os sites estiverem ocupados, esperar ate um liberar (max 30s)
    waited = 0
    while waited < 30:
        available = [s for s in site_order if s not in get_busy_sites()]
        if available:
            break
        log.debug(f"Todos os {len(site_order)} sites ocupados, esperando... ({waited}s)")
        time.sleep(2)
        waited += 2

    for site_key in site_order:
        site = sites.get(site_key)
        if not site or not site.get("enabled"):
            continue

        # Pular sites que ja estao baixando algo (paralelismo entre sites)
        if not acquire_site(site_key, serial):
            busy = get_busy_sites()
            log.debug(f"Site {site_key} ocupado por {busy.get(site_key,'?')}, pulando")
            continue

        queue_update_phase(serial, "searching", site_key, "buscando...")

        try:
            result = None
            detail = ""
            if site_key == "cdromance":
                result, detail = navigator.search_cdromance(short_query, serial, name)
            elif site_key == "vimm":
                # Tentar cache primeiro (sem Playwright, via requests)
                result, detail = navigator.search_vimm_cache(serial, name)
                if result is None:
                    # Fallback: navegar com Playwright
                    result, detail = navigator.search_vimm(short_query, serial, name)
            elif site_key == "archive_org":
                result, detail = navigator.search_archive_org(short_query, serial, name)
            elif site_key == "archive_org_jp":
                result, detail = navigator.search_archive_org_jp(short_query, serial, name)
            elif site_key == "psxdatacenter_jp":
                result, detail = navigator.search_psxdatacenter_jp(short_query, serial, name)
            elif site_key == "retrostic_jp":
                result, detail = navigator.search_retrostic_jp(short_query, serial, name)
            elif site_key == "romsfun":
                result, detail = navigator.search_romsfun(short_query, serial, name)
            elif site_key == "romspedia":
                result, detail = navigator.search_romspedia(short_query, serial, name)
            elif site_key == "retroiso":
                result, detail = navigator.search_retroiso(short_query, serial, name)
            elif site_key == "retromania":
                result, detail = navigator.search_retromania(short_query, serial, name)
            elif site_key == "vimm":
                result, detail = navigator.search_vimm_cache(serial, name)
                if result is None:
                    result, detail = navigator.search_vimm(short_query, serial, name)
            else:
                # Site generico: navegar pela busca e procurar links de ROM
                search_url = site.get("search_url", "").replace("{query}", quote_plus(short_query))
                if search_url:
                    ok, err = navigator._safe_goto(search_url)
                    if not ok:
                        # Se paywall/bloqueio/malware/403/451, blacklistar imediatamente
                        if any(x in err for x in ["paywall", "bloqueado", "malware", "HTTP 403", "HTTP 451"]):
                            add_to_blacklist(blacklist, site_key=site_key, reason=f"{err}")
                            site["enabled"] = False
                            save_sites(sites)
                            log.warning(f"Site {site_key} blacklisted: {err}")
                            continue
                        # Outros erros (timeout, conexao): incrementar fail_count mas NAO blacklistar
                        # So desativar temporariamente se chegar no limite
                        site["fail_count"] = site.get("fail_count", 0) + 1
                        if site["fail_count"] >= site.get("max_fails", 50):
                            site["enabled"] = False
                            log.warning(f"Site {site_key} desativado por {site['fail_count']} falhas de conexao")
                        save_sites(sites)
                        continue
                    if ok:
                        time.sleep(1)
                        soup = BeautifulSoup(navigator.page.content(), "lxml")
                        # Procurar links que parecam paginas de jogo ou download direto
                        name_lower = short_query.lower()
                        name_words = [w for w in re.sub(r"[^a-z0-9\s]", "", name_lower).split() if len(w) > 2]
                        serial_lower = serial.lower().replace("-", "") if serial else ""
                        best_links = []
                        for a in soup.find_all("a", href=True):
                            href = a["href"]
                            text = a.get_text(strip=True).lower()
                            # Link direto para ROM
                            if any(href.endswith(ext) for ext in ARCHIVE_EXTS) or any(href.endswith(ext) for ext in ROM_EXTS):
                                full_url = urljoin(search_url, href)
                                result = ("direct_url", full_url)
                                detail = f"{site_key}: download direto"
                                break
                            # Link para pagina de jogo (match por nome ou serial)
                            if "/rom" in href.lower() or "/game" in href.lower() or "/download" in href.lower():
                                score = sum(1 for w in name_words if w in text)
                                if serial_lower and serial_lower in text.replace("-", "").replace("_", ""):
                                    score += 5
                                if score > 0:
                                    best_links.append((href, text, score))
                        if result is None and best_links:
                            best_links.sort(key=lambda x: x[2], reverse=True)
                            result = ("page_url", urljoin(search_url, best_links[0][0]))
                            detail = f"{site_key}: {best_links[0][1][:40]}"

            if result is None:
                # "Nao encontrado" NAO é falha de site — so paywall/malware/conteudo falso
                # NAO incrementar fail_count, NAO blacklistar
                record_site_result(site_key, success=False)
                continue

            queue_update_phase(serial, "starting", site_key, detail)

            dl_result = None
            dl_detail = ""
            dl_t0 = time.time()
            if result[0] == "direct_url":
                dl_result, dl_detail = navigator.download_direct_url(result[1], serial)
            elif result[0] == "archive_item":
                dl_result, dl_detail = navigator.download_archive_item(result[1], serial, name)
            elif result[0] == "page_url":
                ok, err = navigator._safe_goto(result[1])
                if ok:
                    soup = BeautifulSoup(navigator.page.content(), "lxml")
                    found = False
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        text = a.get_text(strip=True).lower()
                        if any(href.endswith(ext) for ext in ARCHIVE_EXTS):
                            full_url = urljoin(result[1], href)
                            dl_result, dl_detail = navigator.download_direct_url(full_url, serial)
                            found = True
                            break
                        if "download" in text and href.startswith("http"):
                            dl_result, dl_detail = navigator.download_via_browser(href, serial)
                            if dl_result:
                                found = True
                                break
                    if not found:
                        dl_result, dl_detail = None, "sem link de download na pagina"

            if dl_result is None:
                log.warning(f"Download falhou ({site_key}): {dl_detail[:200]}")
                # "Nao encontrado" / "sem link" NAO é falha de site — so incrementar se for erro real
                # Erros reais: timeout, HTTP 5xx, arquivo muito pequeno, conexao recusada
                if any(x in dl_detail.lower() for x in ["timeout", "http 5", "http 4", "recusada", "connection", "muito pequeno", "muito pequena"]):
                    site["fail_count"] = site.get("fail_count", 0) + 1
                    save_sites(sites)
                record_site_result(site_key, success=False)
                continue

            queue_update_phase(serial, "verifying", site_key, "verificando...")
            valid, verify_msg = verify_download(dl_result)
            if not valid:
                try:
                    dl_result.unlink()
                except:
                    pass
                site["fail_count"] = site.get("fail_count", 0) + 1
                save_sites(sites)
                record_site_result(site_key, success=False)
                continue

            extracted = extract_rom(dl_result, PSX_DIR, serial=serial, name=name)
            if extracted:
                try:
                    dl_result.unlink()
                except:
                    pass
                queue_mark_success(serial, extracted, site_key)
                try:
                    download_cover(serial, name)
                except Exception:
                    pass
                site["fail_count"] = 0
                save_sites(sites)
                dl_elapsed = time.time() - dl_t0
                dl_speed = dl_result.stat().st_size / dl_elapsed if dl_elapsed > 0 else 0
                record_site_result(site_key, success=True, speed=dl_speed)
                return True
            else:
                try:
                    dl_result.unlink()
                except:
                    pass
                record_site_result(site_key, success=False)

        except Exception as e:
            log.error(f"Erro em {site_key}: {e}")
            site["fail_count"] = site.get("fail_count", 0) + 1
            save_sites(sites)
            record_site_result(site_key, success=False)
        finally:
            release_site(site_key, serial)

    # Google fallback com multiplas queries e reativacao de site
    queue_update_phase(serial, "searching", "google", "buscando no Google...")
    try:
        queries = make_search_queries(name, serial)
        for q in queries:
            result, detail = navigator.search_google(q, serial, name)
            if result:
                discovered_site_key = result[2] if len(result) > 2 else None
                queue_update_phase(serial, "starting", "google", detail)
                dl_result = None
                # Se o Google apontou para um site da lista, tentar handler especifico e reativar temporariamente
                if discovered_site_key and discovered_site_key in sites:
                    target_site = sites[discovered_site_key]
                    was_enabled = target_site.get("enabled", False)
                    if not was_enabled:
                        target_site["enabled"] = True
                        target_site["fail_count"] = 0
                        save_sites(sites)
                        log.info(f"Google reativou site {discovered_site_key} para {serial}")
                    try:
                        handler = getattr(navigator, f"search_{discovered_site_key}", None)
                        if handler:
                            sub_result, sub_detail = handler(q, serial, name)
                            if sub_result:
                                queue_update_phase(serial, "starting", discovered_site_key, sub_detail)
                                if sub_result[0] == "direct_url":
                                    dl_result, dl_detail = navigator.download_direct_url(sub_result[1], serial)
                                elif sub_result[0] == "archive_item":
                                    dl_result, dl_detail = navigator.download_archive_item(sub_result[1], serial, name)
                                elif sub_result[0] == "page_url":
                                    ok, err = navigator._safe_goto(sub_result[1])
                                    if ok:
                                        soup = BeautifulSoup(navigator.page.content(), "lxml")
                                        for a in soup.find_all("a", href=True):
                                            href = a["href"]
                                            if any(href.endswith(ext) for ext in ARCHIVE_EXTS):
                                                dl_result, dl_detail = navigator.download_direct_url(urljoin(sub_result[1], href), serial)
                                                break
                                if dl_result:
                                    log.info(f"Download via handler reativado {discovered_site_key}: {sub_detail}")
                    except Exception as e:
                        log.warning(f"Handler reativado {discovered_site_key} falhou: {e}")
                # Fallback direto do Google caso o handler reativado nao funcione
                if dl_result is None:
                    if result[0] == "direct_url":
                        dl_result, dl_detail = navigator.download_direct_url(result[1], serial)
                    elif result[0] == "page_url":
                        ok, err = navigator._safe_goto(result[1])
                        if ok:
                            soup = BeautifulSoup(navigator.page.content(), "lxml")
                            for a in soup.find_all("a", href=True):
                                href = a["href"]
                                if any(href.endswith(ext) for ext in ARCHIVE_EXTS):
                                    dl_result, dl_detail = navigator.download_direct_url(urljoin(result[1], href), serial)
                                    break
                    elif result[0] == "archive_item":
                        dl_result, dl_detail = navigator.download_archive_item(result[1], serial, name)
                if dl_result:
                    valid, _ = verify_download(dl_result)
                    if valid:
                        extracted = extract_rom(dl_result, PSX_DIR, serial=serial, name=name)
                        if extracted:
                            try:
                                dl_result.unlink()
                            except:
                                pass
                            queue_mark_success(serial, extracted, discovered_site_key or "google")
                            try:
                                download_cover(serial, name)
                            except Exception:
                                pass
                            record_site_result(discovered_site_key or "google", success=True)
                            return True
                # Se achou URL mas nao baixou, tentar proxima query
                continue
    except Exception as e:
        log.error(f"Erro no Google: {e}")

    queue_mark_failed(serial, "todos os sites + google falharam")
    return False


def _setup_worker_logging(worker_id, prefix):
    """Configura logging para workers: garante que mensagens vao para o arquivo principal."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter(f"%(asctime)s [{prefix}{worker_id}] [%(levelname)s] %(message)s")
    # Se ja tem handlers, reutilizar; senao adicionar file handler
    has_file = any(isinstance(h, logging.FileHandler) for h in root.handlers)
    if not has_file:
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    # Logger com nome unico para evitar conflitos
    wlog = logging.getLogger(f"{prefix}-{worker_id}")
    wlog.setLevel(logging.INFO)
    if not wlog.handlers:
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setFormatter(fmt)
        wlog.addHandler(fh)
    # Garantir que propagacao para o root nao duplique no stdout defeituoso
    wlog.propagate = False
    return wlog


def downloader_process(worker_id, limit, headless):
    """Downloader puro: so baixa itens com URL pronta no buffer.
    NAO faz busca — espera o buffer ser alimentado pelos searchers.
    """
    wlog = _setup_worker_logging(worker_id, "DL")
    init_queue()
    wlog.info(f"Downloader {worker_id} iniciado")

    processed = 0
    pw = None
    navigator = None

    def ensure_navigator():
        """Inicializa Playwright lazy — so quando necessario (download via browser)."""
        nonlocal pw, navigator
        if navigator is None:
            pw = sync_playwright().start()
            navigator = SiteNavigator(pw)
            wlog.info(f"Playwright OK (lazy)")
        return navigator

    try:
        wlog.info(f"Downloader {worker_id} iniciado (sem Playwright — lazy)")
        set_current_worker_id(worker_id)

        while True:
            action, paused = check_control()
            if action == "stop":
                wlog.info("Stop recebido")
                break
            if action == "pause" or paused:
                time.sleep(2)
                continue

            if limit and processed >= limit:
                wlog.info(f"Limite {limit} alcancado")
                break

            # Worker fica idle e espera o robot atribuir um item
            set_worker_idle(worker_id)
            item = queue_next_item(worker_id)
            if item is None:
                # Nenhum item atribuido ainda — baixar capas enquanto espera
                if int(time.time()) % 30 == 0:
                    wlog.info(f"DL{worker_id}: aguardando atribuicao do robot")
                dl_cover_next(wlog)
                time.sleep(0.5)
                continue

            serial = item["serial"]
            wlog.info(f"DL{worker_id}: INICIO ITERACAO — item pego {serial} name={item.get('name','')[:60]}")

            # Obter URL: pre-buscada do buffer ou busca on-the-fly
            search_result = None
            if item.get('_needs_search'):
                wlog.info(f"DL{worker_id}: buscando URL on-the-fly para {serial}")
                sites = load_sites()
                blacklist = load_blacklist()
                search_result = search_item_for_downloader(serial, item["name"], sites, blacklist)
            else:
                wlog.info(f"DL{worker_id}: tentando URL pre-buscada para {serial}")
                search_result = get_presearched_url(serial)
                if not search_result:
                    wlog.info(f"DL{worker_id}: URL nao pre-buscada para {serial} — tentando busca on-the-fly")
                    sites = load_sites()
                    blacklist = load_blacklist()
                    search_result = search_item_for_downloader(serial, item["name"], sites, blacklist)
                else:
                    wlog.info(f"DL{worker_id}: pre-search hit para {serial}")
            if not search_result:
                wlog.info(f"DL{worker_id}: nenhuma URL encontrada para {serial}")
                queue_mark_failed(serial, "nenhuma URL encontrada")
                continue

            if not search_result or search_result[0] is None:
                wlog.warning(f"DL{worker_id}: nenhuma URL encontrada para {serial}")
                queue_mark_failed(serial, "nenhuma URL encontrada")
                continue

            result_type, url, site_key, detail = search_result
            if not result_type or not url or not site_key:
                wlog.warning(f"DL{worker_id}: resultado de busca invalido para {serial}: {search_result}")
                queue_mark_failed(serial, "resultado de busca invalido")
                continue
            wlog.info(f"DL{worker_id}: Baixando {serial} via {site_key} ({result_type}) url={str(url)[:100]}")
            queue_update_phase(serial, "starting", site_key, detail[:80])

            wlog.info(f"DL{worker_id}: found {serial} via {site_key}, acquiring...")
            # search_item_for_downloader ja reservou o site; evitar double-acquire
            already_acquired = False
            with _BUSY_SITES_LOCK:
                already_acquired = serial in _BUSY_SITES.get(site_key, [])
            if not already_acquired:
                if not acquire_site(site_key, serial):
                    wlog.info(f"DL{worker_id}: site {site_key} ocupado — devolvendo item {serial}")
                    queue_return_item(item)
                    continue

            try:
                wlog.info(f"DL{worker_id}: chamando download para {serial} ({result_type})")
                dl_result = None
                dl_msg = ""
                if result_type == "direct_url":
                    # requests puro — nao precisa de Playwright
                    dl_result, dl_msg = SiteNavigator.download_direct_url(None, url, serial)
                    # CoolROM links expiram (HTTP 403/400); refresh via pagina de detalhe
                    if not dl_result and site_key == "coolrom" and ("403" in dl_msg or "400" in dl_msg or "Bad Request" in dl_msg):
                        wlog.info(f"DL{worker_id}: coolrom link expirou para {serial} — refresh")
                        fresh_url = SiteNavigator.refresh_coolrom_link(None, serial, item["name"])
                        if fresh_url:
                            wlog.info(f"DL{worker_id}: novo link coolrom obtido para {serial}")
                            dl_result, dl_msg = SiteNavigator.download_direct_url(None, fresh_url, serial)
                elif result_type == "archive_item":
                    # requests puro — nao precisa de Playwright
                    dl_result, dl_msg = SiteNavigator.download_archive_item(None, url, serial, item["name"])
                else:
                    # download_via_browser precisa de Playwright
                    nav = ensure_navigator()
                    dl_result, dl_msg = nav.download_via_browser(url, serial)

                wlog.info(f"DL{worker_id}: download retornou para {serial}: result={dl_result is not None} msg={dl_msg[:120]}")
                if dl_result:
                    verified, verify_msg = verify_download(dl_result)
                    wlog.info(f"DL{worker_id}: verify {serial}: {verified} — {verify_msg[:120]}")
                    if verified:
                        extracted = extract_rom(dl_result, PSX_DIR, serial, item["name"])
                        wlog.info(f"DL{worker_id}: extract {serial}: {extracted}")
                        if extracted:
                            try:
                                dl_result.unlink()
                            except:
                                pass
                            if item.get("type") == "homebrew":
                                extracted = finalize_homebrew_path(extracted, serial, item["name"])
                        queue_mark_success(serial, str(extracted or dl_result), site_key)
                        wlog.info(f"SUCESSO: {serial} via {site_key} — {verify_msg}")
                        processed += 1
                    else:
                        wlog.warning(f"Verify falhou ({site_key}): {verify_msg}")
                        try:
                            dl_result.unlink()
                        except:
                            pass
                else:
                    wlog.warning(f"Download falhou ({site_key}): {dl_msg[:200]}")
            except Exception as e:
                wlog.error(f"Erro download {serial}: {e}")
            finally:
                release_site(site_key, serial)
                queue_clear_progress(serial)
                time.sleep(0.5)
                # CoolROM bloqueia por volume; respeitar intervalo entre downloads
                if site_key == "coolrom":
                    time.sleep(5)

    except Exception as e:
        wlog.error(f"Erro no downloader: {e}")
    finally:
        if navigator:
            try:
                navigator.close()
            except Exception:
                pass
        if pw:
            try:
                pw.stop()
            except Exception:
                pass
    wlog.info(f"Downloader {worker_id} finalizado — {processed} itens")
    return processed


def worker_process(worker_id, limit, headless):
    set_current_worker_id(worker_id)
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [W{worker_id}] [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            SafeStreamHandler(sys.stdout),
        ],
    )
    wlog = logging.getLogger(f"worker-{worker_id}")
    init_queue()
    cleanup_stale_items(max_age_seconds=300)
    wlog.info(f"Worker {worker_id} iniciado")

    # Debug: verificar estado da fila
    data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}})
    wlog.info(f"Fila tem {len(data.get('queue', []))} itens")

    processed = 0
    pw = None
    navigator = None
    try:
        # Padrao oficial: sync_playwright().start() por thread (nao usar with)
        pw = sync_playwright().start()
        navigator = SiteNavigator(pw)
        wlog.info(f"Playwright OK")

        while True:
            action, paused = check_control()
            if action == "stop":
                wlog.info("Stop recebido")
                break
            if action == "pause" or paused:
                time.sleep(2)
                continue

            set_worker_idle(worker_id)
            item = queue_next_item(worker_id)
            if item is None:
                wlog.info(f"next_item retornou None — verificando pending...")
                time.sleep(0.5)
                has = queue_has_pending()
                wlog.info(f"has_pending: {has}")
                if not has:
                    break
                continue

            wlog.info(f"Item pego: {item['serial']}")

            if limit and processed >= limit:
                queue_return_item(item)
                wlog.info(f"Limite {limit} alcancado — devolvendo item")
                break

            wlog.info(f"Processando: {item['serial']} — {item['name']}")
            sites = load_sites()
            blacklist = load_blacklist()
            process_item(item, navigator, sites, blacklist)
            processed += 1
            time.sleep(1)

    except Exception as e:
        wlog.error(f"Erro no worker: {e}")
    finally:
        if navigator:
            try:
                navigator.close()
            except Exception:
                pass
        if pw:
            try:
                pw.stop()
            except Exception:
                pass
    wlog.info(f"Worker {worker_id} finalizado — {processed} itens")
    return processed


class DashboardServer:
    """Servidor HTTP em subprocesso separado (nao importa Playwright)."""
    def __init__(self):
        self._proc = None

    def start(self):
        global SERVER_PORT
        server_script = Path(__file__).parent / "importre_server.py"
        # Matar servidores antigos na porta antes de iniciar
        try:
            import subprocess as sp
            for port in [SERVER_PORT, SERVER_PORT + 1, SERVER_PORT + 2]:
                sp.run(
                    ["powershell", "-WindowStyle", "Hidden", "-Command",
                     f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
                     "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
                    capture_output=True, timeout=5, **get_no_window_kwargs()
                )
        except Exception:
            pass
        for port in [SERVER_PORT, SERVER_PORT + 1, SERVER_PORT + 2]:
            try:
                import subprocess as sp
                kwargs = get_no_window_kwargs()
                self._proc = sp.Popen(
                    [sys.executable, str(server_script), str(port)],
                    **kwargs,
                )
                time.sleep(1.5)
                if self._proc.poll() is None:
                    SERVER_PORT = port
                    log.info(f"Servidor: http://{SERVER_HOST}:{SERVER_PORT} (PID {self._proc.pid})")
                    return
                else:
                    log.warning(f"Porta {port} falhou, tentando proxima...")
            except Exception as e:
                log.warning(f"Erro ao iniciar servidor na porta {port}: {e}")
        log.warning("Nao foi possivel iniciar servidor HTTP")

    def stop(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                pass


def generate_dashboard_html():
    """Gera HTML estatico com JS que faz poll da API."""
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Importre — Download de ROMs PSX</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 0; padding-top: 130px; }
h2 { color: #e94560; margin-bottom: 8px; font-size: 15px; }
/* === HEADER FIXO === */
.header-fixed { position: fixed; top: 0; left: 0; right: 0; z-index: 1000; background: #16213e; box-shadow: 0 2px 10px rgba(0,0,0,0.5); }
/* Linha 1: joystick + titulo + status + estado + botoes */
.header-row1 { display: flex; align-items: center; gap: 10px; padding: 6px 16px; flex-wrap: nowrap; }
.header-title { font-size: 16px; font-weight: bold; color: #e94560; white-space: nowrap; }
.header-spacer { flex: 1; }
.header-update { font-size: 11px; color: #888; white-space: nowrap; }
.server-status { padding: 3px 10px; border-radius: 5px; font-weight: bold; font-size: 11px; white-space: nowrap; }
.server-online { background: #4ecca3; color: #1a1a2e; }
.server-offline { background: #e94560; color: #fff; }
.control-state { font-size: 12px; font-weight: bold; padding: 4px 12px; border-radius: 6px; background: #0f3460; white-space: nowrap; }
.state-running { color: #4ecca3; }
.state-paused { color: #f0a500; }
.state-stopped { color: #e94560; }
.state-idle { color: #4fc3f7; }
.control-buttons { display: flex; gap: 6px; }
.btn { padding: 5px 14px; border: none; border-radius: 6px; font-size: 12px; font-weight: bold; cursor: pointer; transition: all 0.2s; white-space: nowrap; }
.btn:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
.btn:disabled { opacity: 0.3; cursor: not-allowed; transform: none; }
.btn-start { background: #4ecca3; color: #1a1a2e; }
.btn-pause { background: #f0a500; color: #1a1a2e; }
.btn-restart { background: #4fc3f7; color: #1a1a2e; }
.btn-stop { background: #e94560; color: #fff; }
/* Linha 2: progresso + cards */
.header-row2 { display: flex; align-items: center; gap: 10px; padding: 4px 16px 6px; flex-wrap: wrap; }
.progress-bar { flex: 1; min-width: 200px; height: 16px; background: #333; border-radius: 8px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #e94560, #4ecca3); transition: width 0.5s; }
.progress-text { font-size: 11px; color: #888; white-space: nowrap; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; }
.stat-card { background: #0f3460; padding: 4px 14px; border-radius: 6px; text-align: center; min-width: 80px; }
.stat-card .num { font-size: 18px; font-weight: bold; }
.stat-card .label { font-size: 9px; color: #888; text-transform: uppercase; margin-top: 1px; }
.stat-pending .num { color: #f0a500; }
.stat-success .num { color: #4ecca3; }
.stat-failed .num { color: #e94560; }
.stat-searching .num { color: #4fc3f7; }
.stat-downloading .num { color: #ba68c8; }
.stat-skipped .num { color: #78909c; }
/* === CONTEUDO === */
.content { padding: 12px 16px; }
.section { margin-top: 15px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 5px 10px; text-align: left; border-bottom: 1px solid #333; font-size: 12px; }
th { background: #16213e; color: #e94560; text-transform: uppercase; font-size: 10px; position: sticky; top: 0; }
tr:hover { background: #16213e; }
.status-searching { color: #4fc3f7; }
.status-downloading { color: #ba68c8; }
.status-verifying { color: #4ecca3; }
.status-success { color: #4ecca3; }
.status-failed { color: #e94560; }
.site-enabled { color: #4ecca3; }
.site-disabled { color: #f0a500; }
.site-blacklisted { color: #e94560; }
.unrecoverable { background: #3d0000; padding: 8px; border-radius: 5px; margin: 8px 0; }
.sites-panel { background: #16213e; border-radius: 8px; padding: 4px; }
.fail-bar { width: 50px; height: 5px; background: #333; border-radius: 3px; overflow: hidden; display: inline-block; }
.fail-fill { height: 100%; }
.footer { margin-top: 20px; padding: 10px; background: #16213e; border-radius: 6px; text-align: center; font-size: 11px; }
.toast { position: fixed; top: 60px; right: 20px; padding: 12px 20px; border-radius: 6px; font-weight: bold; z-index: 9999; opacity: 0; transition: opacity 0.3s; pointer-events: none; font-size: 12px; }
.toast.show { opacity: 1; }
#refresh-indicator { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #4ecca3; margin-left: 5px; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
/* === SCROLL DAS SECOES === */
.scroll-area { max-height: 50vh; overflow-y: auto; border: 1px solid #333; border-radius: 6px; }
.scroll-area table thead th { position: sticky; top: 0; z-index: 2; }
.scroll-area::-webkit-scrollbar { width: 8px; }
.scroll-area::-webkit-scrollbar-track { background: #1a1a2e; }
.scroll-area::-webkit-scrollbar-thumb { background: #e94560; border-radius: 4px; }
.success-scroll { max-height: 50vh; overflow-y: auto; border: 1px solid #333; border-radius: 6px; }
.success-scroll table thead th { position: sticky; top: 0; z-index: 2; }
.success-scroll::-webkit-scrollbar { width: 8px; }
.success-scroll::-webkit-scrollbar-track { background: #1a1a2e; }
.success-scroll::-webkit-scrollbar-thumb { background: #e94560; border-radius: 4px; }
.stat-covers .num { color: #4fc3f7; }
</style>
</head>
<body>

<div class="header-fixed">
    <div class="header-row1">
        <span style="font-size:20px">🎮</span>
        <span class="header-title">Importre — PSX</span>
        <span class="header-update">⏱ <span id="last-update">—</span><span id="refresh-indicator"></span></span>
        <span id="server-status" class="server-status server-offline">OFF</span>
        <span id="control-state" class="control-state state-idle">—</span>
        <span class="header-spacer"></span>
        <div class="control-buttons">
            <button class="btn btn-start" onclick="sendControl('start')">▶️</button>
            <button class="btn btn-pause" onclick="sendControl('pause')">⏸️</button>
            <button class="btn btn-restart" onclick="sendControl('restart')">🔄</button>
            <button class="btn btn-stop" onclick="sendControl('stop')">🛑</button>
        </div>
    </div>
    <div class="header-row2">
        <div class="progress-bar"><div id="progress-fill" class="progress-fill" style="width:0%"></div></div>
        <span id="progress-text" class="progress-text">0/0 (0%)</span>
        <div class="stats">
            <div class="stat-card stat-pending"><div class="num" id="stat-pending">0</div><div class="label">Pend.</div></div>
            <div class="stat-card stat-searching"><div class="num" id="stat-searching">0</div><div class="label">Busca</div></div>
            <div class="stat-card stat-downloading"><div class="num" id="stat-downloading">0</div><div class="label">DL</div></div>
            <div class="stat-card stat-success"><div class="num" id="stat-success">0</div><div class="label">OK</div></div>
            <div class="stat-card stat-failed"><div class="num" id="stat-failed">0</div><div class="label">Fail</div></div>
            <div class="stat-card stat-skipped"><div class="num" id="stat-skipped">0</div><div class="label">Skip</div></div>
            <div class="stat-card stat-covers"><div class="num" id="stat-covers">0</div><div class="label">Capas</div></div>
        </div>
    </div>
</div>

<div class="content">

<div class="section">
<h2>🔄 Em Andamento</h2>
<div class="scroll-area">
<table><thead><tr><th>Serial</th><th>Jogo</th><th>Status</th><th>Site</th><th>Detalhe</th></tr></thead>
<tbody id="in-progress-rows"><tr><td colspan="5" style="text-align:center;color:#888">—</td></tr></tbody></table>
</div>
</div>

<div class="section">
<h2>✅ Sucessos</h2>
<div class="success-scroll">
<table><thead><tr><th>Serial</th><th>Jogo</th><th>Site</th><th>Capa</th><th>Quando</th></tr></thead>
<tbody id="success-rows"><tr><td colspan="5" style="text-align:center;color:#888">—</td></tr></tbody></table>
</div>
</div>

<div class="section" id="failed-section" style="display:none">
<h2>❌ Itens Irrecuperáveis</h2>
<div class="unrecoverable"><table><thead><tr><th>Serial</th><th>Jogo</th><th>Motivo</th></tr></thead>
<tbody id="failed-rows"></tbody></table></div>
</div>

<div class="section">
<h2>🌐 Status dos Sites</h2>
<div class="sites-panel"><table><thead><tr><th>Site</th><th>URL</th><th>Status</th><th>Ocupado</th><th>Falhas</th><th>Veloc.</th><th>Taxa</th></tr></thead>
<tbody id="sites-rows"></tbody></table></div>
</div>

<div class="footer">
    <p id="footer-count">Total: 0 | Processados: 0 | Restantes: 0</p>
    <p style="color:#888;font-size:11px;margin-top:5px">importre.py | Servidor: http://127.0.0.1:8765</p>
</div>

<div id="toast" class="toast"></div>

<script>
var API = 'http://127.0.0.1:8765';

function showToast(msg, color) {
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.style.background = color || '#4ecca3';
    t.style.color = '#1a1a2e';
    t.classList.add('show');
    setTimeout(function() { t.classList.remove('show'); }, 3000);
}

function sendControl(action) {
    fetch(API + '/api/control/' + action)
        .then(function(r) { return r.json(); })
        .then(function() {
            showToast('Comando "' + action + '" enviado!', '#4ecca3');
            refresh();
        })
        .catch(function() {
            showToast('Servidor offline!', '#e94560');
        });
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function refresh() {
    var ctrl = new AbortController();
    var t = setTimeout(function() { ctrl.abort(); }, 5000);
    fetch(API + '/api/status', {signal: ctrl.signal})
        .then(function(r) { return r.json(); })
        .then(function(data) {
            clearTimeout(t);
            document.getElementById('server-status').textContent = '🟢 ON';
            document.getElementById('server-status').className = 'server-status server-online';
            updateUI(data);
        })
        .catch(function() {
            clearTimeout(t);
            document.getElementById('server-status').textContent = '🔴 OFF';
            document.getElementById('server-status').className = 'server-status server-offline';
            var el = document.getElementById('control-state');
            el.textContent = 'offline';
            el.className = 'control-state state-stopped';
            document.querySelector('.btn-start').disabled = true;
            document.querySelector('.btn-pause').disabled = true;
            document.querySelector('.btn-stop').disabled = true;
        });
}

function updateUI(data) {
    var s = data.status;
    var ctrl = data.control;
    var ps = data.process_state;

    // Estado
    var stateLabels = {running: '▶️ Rodando', paused: '⏸️ Pausado', stopped: '🛑 Parado', idle: '⏳ Aguardando'};
    var stateColors = {running: 'state-running', paused: 'state-paused', stopped: 'state-stopped', idle: 'state-idle'};
    var el = document.getElementById('control-state');
    el.textContent = stateLabels[ps] || '—';
    el.className = 'control-state ' + (stateColors[ps] || 'state-idle');

    // Botoes
    document.querySelector('.btn-start').disabled = (ps === 'running');
    document.querySelector('.btn-pause').disabled = (ps !== 'running');
    document.querySelector('.btn-stop').disabled = (ps === 'stopped');

    // Progresso
    var processed = s.completed + s.failed;
    var total = s.total || (s.pending + s.in_progress + s.completed + s.failed);
    var pct = total > 0 ? (processed / total * 100) : 0;
    document.getElementById('progress-fill').style.width = pct.toFixed(1) + '%';
    document.getElementById('progress-text').textContent = processed + '/' + total + ' (' + pct.toFixed(1) + '%)';

    // Stats
    document.getElementById('stat-pending').textContent = s.pending;
    document.getElementById('stat-searching').textContent = s.searching;
    document.getElementById('stat-downloading').textContent = s.downloading;
    document.getElementById('stat-success').textContent = s.completed;
    document.getElementById('stat-failed').textContent = s.failed;
    document.getElementById('stat-skipped').textContent = s.skipped || 0;
    document.getElementById('stat-covers').textContent = data.cover_count || 0;

    // Em andamento
    var ipHtml = '';
    var ipItems = s.in_progress_items || {};
    if (Object.keys(ipItems).length === 0) {
        ipHtml = '<tr><td colspan="5" style="text-align:center;color:#888">Nenhum item em andamento</td></tr>';
    } else {
        for (var serial in ipItems) {
            var item = ipItems[serial];
            var phase = item._phase || 'searching';
            var icons = {searching: '🔍', downloading: '⬇️', verifying: '✅'};
            ipHtml += '<tr><td>' + esc(serial) + '</td><td>' + esc(item.name) + '</td>' +
                '<td class="status-' + phase + '">' + (icons[phase]||'⏳') + ' ' + phase + '</td>' +
                '<td>' + esc(item._current_site || '—') + '</td><td>' + esc(item._detail || '—') + '</td></tr>';
        }
    }
    document.getElementById('in-progress-rows').innerHTML = ipHtml;

    // Sucessos
    var suHtml = '';
    var suItems = s.completed_items || {};
    var coversInfo = data.covers_info || {};
    if (Object.keys(suItems).length === 0) {
        suHtml = '<tr><td colspan="5" style="text-align:center;color:#888">Nenhum sucesso ainda</td></tr>';
    } else {
        for (var serial in suItems) {
            var info = suItems[serial];
            var hasCover = coversInfo[serial];
            var coverIcon = hasCover ? '🖼️' : '❌';
            suHtml += '<tr><td>' + esc(serial) + '</td><td>' + esc(info.name) + '</td>' +
                '<td>' + esc(info.site || '—') + '</td><td>' + coverIcon + '</td><td>' + esc((info.timestamp||'').slice(0,19)) + '</td></tr>';
        }
    }
    document.getElementById('success-rows').innerHTML = suHtml;

    // Falhas
    var faItems = s.failed_items || {};
    if (Object.keys(faItems).length > 0) {
        document.getElementById('failed-section').style.display = 'block';
        var faHtml = '';
        for (var serial in faItems) {
            var info = faItems[serial];
            faHtml += '<tr><td>' + esc(serial) + '</td><td>' + esc(info.name) + '</td><td>' + esc(info.reason) + '</td></tr>';
        }
        document.getElementById('failed-rows').innerHTML = faHtml;
    } else {
        document.getElementById('failed-section').style.display = 'none';
    }

    // Sites
    var sitesHtml = '';
    var sites = data.sites || {};
    var bl = data.blacklist || {sites: []};
    var learn = data.learning || {site_stats: {}};
    var busy = s.busy_sites || {};
    if (Object.keys(sites).length === 0) {
        sitesHtml = '<tr><td colspan="7" style="text-align:center;color:#888">Nenhum site</td></tr>';
    } else {
        for (var key in sites) {
            var site = sites[key];
            var isBl = bl.sites.indexOf(key) >= 0;
            var isEn = site.enabled;
            var statusLabel, statusClass;
            if (isBl) { statusLabel = '🚫 Blacklist'; statusClass = 'site-blacklisted'; }
            else if (isEn) { statusLabel = '✅ Ativo'; statusClass = 'site-enabled'; }
            else { statusLabel = '⚠️ Desativado'; statusClass = 'site-disabled'; }
            var fc = site.fail_count || 0;
            var mf = site.max_fails || 5;
            var fpct = Math.min(fc/mf*100, 100);
            var fcolor = fpct > 80 ? '#e94560' : fpct > 50 ? '#f0a500' : '#4ecca3';
            var stats = learn.site_stats[key] || {attempts: 0, successes: 0, avg_speed: 0};
            var rate = stats.attempts > 0 ? (stats.successes / stats.attempts * 100).toFixed(0) + '%' : '—';
            var speedKB = stats.avg_speed || 0;
            var speedStr = speedKB > 1048576 ? (speedKB/1048576).toFixed(1) + 'MB/s' : speedKB > 1024 ? (speedKB/1024).toFixed(0) + 'KB/s' : '—';
            var busyLabel = busy[key] ? '⬇️ ' + esc(busy[key]) : '—';
            var busyClass = busy[key] ? 'status-downloading' : '';
            sitesHtml += '<tr><td><strong>' + esc(key) + '</strong></td><td><a href="' + esc(site.url) + '" target="_blank" style="color:#4fc3f7">' + esc(site.url) + '</a></td>' +
                '<td class="' + statusClass + '">' + statusLabel + '</td>' +
                '<td class="' + busyClass + '">' + busyLabel + '</td>' +
                '<td><div class="fail-bar"><div class="fail-fill" style="width:' + fpct + '%;background:' + fcolor + '"></div></div> ' + fc + '/' + mf + '</td>' +
                '<td>' + speedStr + '</td>' +
                '<td>' + rate + '</td></tr>';
        }
    }
    document.getElementById('sites-rows').innerHTML = sitesHtml;

    // Footer
    document.getElementById('footer-count').textContent = 'Total: ' + total + ' | Processados: ' + processed + ' | Restantes: ' + s.pending;
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString('pt-BR');
}

// Poll a cada 3 segundos
refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Importre — Download de ROMs PSX")
    parser.add_argument("--status", action="store_true", help="So inicia servidor + dashboard")
    parser.add_argument("--retry-failed", action="store_true", help="Recoloca falhos na fila")
    parser.add_argument("--site", type=str, help="So usa um site")
    parser.add_argument("--limit", type=int, help="Limite de itens por worker")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Workers paralelos")
    parser.add_argument("--rounds", type=int, default=0, help="Rodadas (0=continuo)")
    parser.add_argument("--headless", action="store_true", default=True, help="Browser headless")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Browser visivel")
    parser.add_argument("--no-server", action="store_true", help="Nao inicia servidor HTTP")
    args = parser.parse_args()

    init_queue()
    load_presearch_buffer()  # carregar URLs prontas do buffer anterior
    cleanup_stale_items(max_age_seconds=60)  # limpar itens presos (>1min) antes de iniciar downloaders

    if args.retry_failed:
        fl = file_lock()
        try:
            data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}, "completed": {}, "failed": {}, "retry_count": {}})
            for serial, info in list(data.get("failed", {}).items()):
                data["queue"].append({"serial": serial, "name": info.get("name", ""), "region": "??", "section": "", "type": "commercial"})
                del data["failed"][serial]
            data["retry_count"] = {}
            save_json(QUEUE_PATH, data)
            log.info("Falhos recolocados na fila")
        finally:
            file_unlock(fl)

    if args.site:
        sites = load_sites()
        for key in sites:
            sites[key]["enabled"] = (key == args.site)
        save_sites(sites)

    clear_control()

    # Servidor HTTP (sempre rodando, mesmo em --status)
    server = None
    if not args.no_server:
        server = DashboardServer()
        server.start()

    # Gerar dashboard inicial (apenas se nao existir — preserva dashboard customizado)
    if not DASHBOARD_PATH.exists():
        with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
            f.write(generate_dashboard_html())

    if args.status:
        print(f"\nDashboard: http://{SERVER_HOST}:{SERVER_PORT}")
        print(f"Arquivo: {DASHBOARD_PATH}")
        print("\nPressione Ctrl+C para parar...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nParando...")
        finally:
            if server:
                server.stop()
        return

    # Modo processamento: divisao dinamica entre searchers e downloaders
    # 40% searchers / 60% downloaders: priorizar downloads reais; searchers alimentam buffer
    num_workers = max(12, int(args.workers * 0.6))
    num_searchers = max(8, args.workers - num_workers)
    log.info(f"Importre iniciado — {num_workers} downloaders + {num_searchers} searchers")

    try:
        if args.rounds > 0:
            for round_num in range(1, args.rounds + 1):
                action, _ = check_control()
                if action == "stop":
                    log.info("Stop — encerrando")
                    break
                log.info(f"=== RODADA {round_num}/{args.rounds} ===")
                print(f"\n{'='*60}\nRODADA {round_num}/{args.rounds} — {num_workers} DL + {num_searchers} SEARCH\n{'='*60}\n")
                with ThreadPoolExecutor(max_workers=num_workers) as executor:
                    # Iniciar apenas downloaders (robot cuida da fila)
                    dl_futures = [executor.submit(downloader_process, w, args.limit, args.headless) for w in range(num_workers)]
                    for f in as_completed(dl_futures):
                        log.info(f"Downloader: {f.result()} itens")
        else:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                dl_futures = [executor.submit(downloader_process, w, args.limit, args.headless) for w in range(num_workers)]
                for f in as_completed(dl_futures):
                    log.info(f"Downloader: {f.result()} itens")
    except KeyboardInterrupt:
        log.info("Interrompido")

    # Status final
    status = queue_get_status()
    log.info(f"Concluido: {status['completed']} sucessos, {status['failed']} falhas, {status['pending']} pendentes")
    if status["failed_items"]:
        print(f"\n{'='*60}\n⚠️  {len(status['failed_items'])} itens irrecuperáveis:")
        for serial, info in status["failed_items"].items():
            print(f"  {serial} — {info.get('name', '')} — {info.get('reason', '')}")
        print(f"{'='*60}")

    # Servidor continua rodando apos processamento
    if server:
        print(f"\nDashboard ativo: http://{SERVER_HOST}:{SERVER_PORT}")
        print("Pressione Ctrl+C para parar o servidor...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nParando servidor...")
        finally:
            server.stop()


if __name__ == "__main__":
    import faulthandler
    faulthandler.enable()
    # dump_traceback_later(30, exit=True) desativado — mata o processo quando
    # threads de rede (Tor/SOCKS5) demoram >30s, causando crash constante.
    # O watchdog externo (_watchdog_autonomous.py) já monitora estagnação.
    main()
