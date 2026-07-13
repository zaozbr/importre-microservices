"""
Downloader paralelo RÁPIDO para ROMs do archive.org.
Estratégia:
1. Tenta download DIRETO (sem Tor) primeiro — 10x mais rápido
2. Fallback para Tor se direto falhar
3. Busca em collections específicas do archive.org (redump, psx, etc)
4. Paraleliza múltiplos downloads (4 simultâneos)
"""
import sys, os, time, json, threading, queue as threadqueue, traceback
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r"D:\roms\library\roms\_importre_state"
QUEUE_PATH = os.path.join(STATE_DIR, "queue.json")
DOWNLOADS_DIR = os.path.join(STATE_DIR, "downloads")
DL_PROGRESS_PATH = os.path.join(STATE_DIR, "dl_progress.json")
LOG_PATH = os.path.join(STATE_DIR, "fast_downloader.log")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')

# Collections específicas do archive.org para PSX
ARCHIVE_COLLECTIONS = [
    "psx_redump", "sony_playstation", "playstation_games",
    "redump", "psx", "PS1", "PSX_ROMs",
]

# Session reutilizável para download direto (sem Tor)
_direct_session = requests.Session()
_direct_session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

_progress_lock = threading.Lock()


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except:
        pass


def update_progress(serial, downloaded, total, speed):
    with _progress_lock:
        try:
            with open(DL_PROGRESS_PATH, 'r', encoding='utf-8') as f:
                prog = json.load(f)
        except:
            prog = {}
        prog[serial] = {
            'downloaded': downloaded,
            'total': total,
            'speed': speed,
            'ts': time.time(),
        }
        try:
            with open(DL_PROGRESS_PATH, 'w', encoding='utf-8') as f:
                json.dump(prog, f, ensure_ascii=False)
        except:
            pass


def clear_progress(serial):
    with _progress_lock:
        try:
            with open(DL_PROGRESS_PATH, 'r', encoding='utf-8') as f:
                prog = json.load(f)
        except:
            prog = {}
        prog.pop(serial, None)
        try:
            with open(DL_PROGRESS_PATH, 'w', encoding='utf-8') as f:
                json.dump(prog, f, ensure_ascii=False)
        except:
            pass


def archive_metadata_direct(identifier):
    """Busca metadata do archive.org DIRETO (sem Tor). Retorna dict ou None."""
    for url in [f"http://archive.org/metadata/{identifier}", f"https://archive.org/metadata/{identifier}"]:
        try:
            r = _direct_session.get(url, timeout=(5, 15))
            if r.status_code == 200:
                return r.json()
        except:
            continue
    return None


def archive_metadata_tor(identifier):
    """Busca metadata via Tor (fallback)."""
    try:
        import importre
        r = importre.archive_request("get", f"http://archive.org/metadata/{identifier}",
                                       timeout=(10, 30), headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def archive_metadata(identifier):
    """Busca metadata: direto primeiro, Tor como fallback."""
    data = archive_metadata_direct(identifier)
    if data:
        return data, 'direct'
    data = archive_metadata_tor(identifier)
    if data:
        return data, 'tor'
    return None, None


def search_archive_org_advanced(serial):
    """Busca avançada no archive.org usando a API de search.
    Retorna lista de (identifier, title, score)."""
    # Buscar por serial entre aspas para match exato
    queries = [
        f'"{serial}"',
        serial.replace("-", " "),
        serial.lower(),
    ]

    results = []
    for q in queries:
        url = f"http://archive.org/advancedsearch.php?q={quote(q)}&fl[]=identifier&fl[]=title&fl[]=description&rows=20&page=1&output=json"
        try:
            r = _direct_session.get(url, timeout=(5, 15))
            if r.status_code == 200:
                data = r.json()
                docs = data.get('response', {}).get('docs', [])
                for doc in docs:
                    ident = doc.get('identifier', '')
                    title = doc.get('title', '')
                    # Score: serial no identifier = 100, no title = 80
                    score = 0
                    if serial.lower().replace("-", "") in ident.lower().replace("-", "").replace("_", "").replace(" ", ""):
                        score = 100
                    elif serial.lower() in ident.lower():
                        score = 80
                    elif serial.lower() in title.lower():
                        score = 60
                    if score > 0:
                        results.append((ident, title, score))
        except:
            continue
        if results:
            break  # Já encontramos com a query mais específica

    # Deduplicar por identifier e ordenar por score
    seen = set()
    unique = []
    for ident, title, score in sorted(results, key=lambda x: -x[2]):
        if ident not in seen:
            seen.add(ident)
            unique.append((ident, title, score))
    return unique


def resolve_archive_item(identifier, serial):
    """Dado um identifier, busca metadata e encontra o arquivo ROM correto.
    Retorna (url, method) ou (None, None)."""
    data, method = archive_metadata(identifier)
    if not data:
        return None, None

    files = data.get("files", [])
    if not files:
        return None, None

    serial_lower = serial.lower().replace("-", "")
    serial_underscore = serial.lower().replace("-", "_")

    candidates = []
    for f in files:
        fname = f.get("name", "")
        fname_lower = fname.lower()
        if not any(fname_lower.endswith(ext) for ext in ROM_EXTS):
            continue
        score = 0
        if serial_lower in fname_lower.replace("-", "").replace("_", "").replace(" ", ""):
            score = 100
        elif serial_underscore in fname_lower:
            score = 80
        elif serial_lower in fname_lower:
            score = 60
        if fname_lower.endswith(('.zip', '.7z', '.chd')):
            score += 10
        candidates.append((score, fname))

    if not candidates:
        for f in files:
            fname = f.get("name", "")
            if any(fname.lower().endswith(ext) for ext in ROM_EXTS):
                candidates.append((0, fname))
                break

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: -x[0])
    best_fname = candidates[0][1]
    encoded = quote(best_fname, safe="/")
    url = f"http://archive.org/download/{identifier}/{encoded}"
    return url, method


def download_direct(url, serial, dest_dir):
    """Download direto (sem Tor) com progresso. Retorna (dest_path, msg)."""
    dest = os.path.join(dest_dir, f"{serial}.download")
    try:
        r = _direct_session.get(url, timeout=(10, 30), stream=True)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"

        total = int(r.headers.get('content-length', 0))
        downloaded = 0
        t0 = time.time()
        last_update = 0

        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_update >= 1.0:
                        speed = downloaded / max(now - t0, 0.1)
                        update_progress(serial, downloaded, total, speed)
                        last_update = now

        update_progress(serial, downloaded, total, downloaded / max(time.time() - t0, 0.1))
        return dest, "ok"
    except Exception as e:
        return None, f"erro: {str(e)[:150]}"
    finally:
        clear_progress(serial)


def download_tor(url, serial, dest_dir):
    """Download via Tor (fallback). Retorna (dest_path, msg)."""
    try:
        import importre
    except:
        return None, "importre não disponível"

    dest = os.path.join(dest_dir, f"{serial}.download")

    # Session com Tor
    s = requests.Session()
    s.proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
    s.headers.update({'User-Agent': 'Mozilla/5.0'})

    try:
        r = s.get(url, timeout=(15, 60), stream=True)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"

        total = int(r.headers.get('content-length', 0))
        downloaded = 0
        t0 = time.time()
        last_update = 0

        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=512 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_update >= 1.0:
                        speed = downloaded / max(now - t0, 0.1)
                        update_progress(serial, downloaded, total, speed)
                        last_update = now

        return dest, "ok"
    except Exception as e:
        return None, f"erro tor: {str(e)[:150]}"
    finally:
        clear_progress(serial)


def download_rom(url, serial, dest_dir):
    """Tenta download direto primeiro, fallback Tor."""
    # Tentativa 1: Direto (rápido)
    log(f"  {serial}: tentando download direto...")
    dest, msg = download_direct(url, serial, dest_dir)
    if dest:
        log(f"  {serial}: SUCESSO direto!")
        return dest, msg

    # Tentativa 2: Tor (fallback)
    log(f"  {serial}: direto falhou ({msg[:60]}), tentando Tor...")
    dest, msg = download_tor(url, serial, dest_dir)
    if dest:
        log(f"  {serial}: SUCESSO via Tor!")
        return dest, msg

    return None, msg


def process_one_rom(serial, name, q_completed, q_lock):
    """Processa um ROM: busca no archive.org, resolve, baixa."""
    log(f"=== {serial} ({name[:30]}) ===")

    # 1. Buscar no archive.org (API avançada, direto)
    log(f"  {serial}: buscando no archive.org...")
    results = search_archive_org_advanced(serial)

    if not results:
        log(f"  {serial}: não encontrado no archive.org")
        return False, "não encontrado"

    # 2. Para cada resultado, tentar resolver e baixar
    for ident, title, score in results[:5]:  # Top 5 candidatos
        log(f"  {serial}: candidato: {ident} (score={score})")

        url, method = resolve_archive_item(ident, serial)
        if not url:
            log(f"  {serial}: sem URL para {ident}")
            continue

        log(f"  {serial}: URL encontrada via {method}: {url[:80]}...")

        # 3. Download
        dest, msg = download_rom(url, serial, DOWNLOADS_DIR)
        if dest:
            # Renomear para extensão correta
            try:
                size = os.path.getsize(dest)
                if size < 1024 * 100:  # < 100KB = provavelmente HTML
                    os.remove(dest)
                    log(f"  {serial}: arquivo muito pequeno ({size}B), provavelmente HTML")
                    continue
            except:
                pass

            # Marcar como completado
            with q_lock:
                q_completed.add(serial)
            log(f"  {serial}: COMPLETADO! {os.path.getsize(dest)/1024/1024:.1f}MB")
            return True, "ok"
        else:
            log(f"  {serial}: download falhou: {msg[:80]}")

    return False, "todos candidatos falharam"


def load_pending():
    """Carrega ROMs pendentes da fila, sem duplicatas."""
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)

    pending = q.get('queue', [])
    completed = q.get('completed', {})
    if not isinstance(completed, dict):
        completed = {}
    failed = q.get('failed', {})
    if not isinstance(failed, dict):
        failed = {}
    in_progress = q.get('in_progress', {})
    if not isinstance(in_progress, dict):
        in_progress = {}

    # Deduplicar
    seen = set()
    to_process = []
    for item in pending:
        if isinstance(item, dict):
            s = item.get('serial', '')
            if s and s not in seen and s not in completed and s not in in_progress:
                seen.add(s)
                to_process.append({'serial': s, 'name': item.get('name', '')})

    return to_process, q


def save_queue_status(serial, success, msg, name=''):
    """Atualiza queue.json com resultado."""
    try:
        with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
            q = json.load(f)

        # Remover da fila
        queue = q.get('queue', [])
        q['queue'] = [item for item in queue if not (isinstance(item, dict) and item.get('serial') == serial)]

        # Remover de in_progress
        ip = q.get('in_progress', {})
        if not isinstance(ip, dict):
            ip = {}
        ip.pop(serial, None)

        if success:
            comp = q.get('completed', {})
            if not isinstance(comp, dict):
                comp = {}
            comp[serial] = {
                'serial': serial, 'name': name, 'site': 'archive_org_fast',
                'completed_at': time.time(),
            }
            q['completed'] = comp
        else:
            fl = q.get('failed', {})
            if not isinstance(fl, dict):
                fl = {}
            fl[serial] = {'reason': msg, 'failed_at': time.time(), 'name': name}
            q['failed'] = fl

        q['in_progress'] = ip
        with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
            json.dump(q, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Erro ao salvar queue: {e}")


def main():
    log("=" * 60)
    log("FAST DOWNLOADER — archive.org direto (sem Tor)")
    log("=" * 60)

    to_process, q = load_pending()
    log(f"Pendentes únicos: {len(to_process)}")

    if not to_process:
        log("Nada para processar!")
        return

    # Marcar todos como in_progress
    ip = q.get('in_progress', {})
    if not isinstance(ip, dict):
        ip = {}
    for item in to_process:
        ip[item['serial']] = {**item, '_phase': 'fast_download', '_started_at': time.time()}
    q['in_progress'] = ip
    with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(q, f, ensure_ascii=False, indent=2)

    q_completed = set()
    q_lock = threading.Lock()

    # Processar em paralelo (4 simultâneos)
    MAX_PARALLEL = 4
    log(f"Processando {len(to_process)} ROMs com {MAX_PARALLEL} workers paralelos...")

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
        futures = {}
        for item in to_process:
            serial = item['serial']
            name = item.get('name', '')
            f = executor.submit(process_one_rom, serial, name, q_completed, q_lock)
            futures[f] = (serial, name)

        for f in as_completed(futures):
            serial, name = futures[f]
            try:
                success, msg = f.result()
            except Exception as e:
                success, msg = False, str(e)[:100]

            save_queue_status(serial, success, msg, name)
            log(f"  {serial}: {'OK' if success else 'FAIL'} — {msg[:60]}")

    # Status final
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    p = len(q.get('queue', []))
    ip = len(q.get('in_progress', {}))
    done = len(q.get('completed', {}))
    fail = len(q.get('failed', {}))
    log(f"\nStatus final: pending={p} in_prog={ip} done={done} fail={fail}")


if __name__ == '__main__':
    main()
