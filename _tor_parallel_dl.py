"""
Downloader paralelo via Tor usando múltiplas streams SOCKS5 com Range requests.
Cada stream Tor tem ~250KB in-flight limit, então múltiplas streams paralelas
multiplicam o throughput. Funciona com archive.org (suporta Accept-Ranges: bytes).

Tambem suporta download direto (sem Tor) como fallback rapido.
"""
import sys, os, time, json, threading, re
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r'D:\roms\library\roms\_importre_state'
DOWNLOADS_DIR = os.path.join(STATE_DIR, 'downloads')
QUEUE_PATH = os.path.join(STATE_DIR, 'queue.json')
DL_PROGRESS_PATH = os.path.join(STATE_DIR, 'dl_progress.json')

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

TOR_PROXY = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
NUM_STREAMS = 16  # 16 streams paralelas (aumentado para Tor)
CHUNK_RETRIES = 3
progress_lock = threading.Lock()
_dl_progress_lock = threading.Lock()


def save_dl_progress(serial, downloaded, total, speed):
    """Salva progresso de download em dl_progress.json (thread-safe + atomico)."""
    with _dl_progress_lock:
        try:
            with open(DL_PROGRESS_PATH, 'r') as pf:
                prog = json.load(pf)
        except:
            prog = {}
        prog[serial] = {'downloaded': downloaded, 'total': total, 'speed': speed, 'ts': time.time()}
        tmp = DL_PROGRESS_PATH + '.tmp'
        try:
            with open(tmp, 'w') as pf:
                json.dump(prog, pf)
            os.replace(tmp, DL_PROGRESS_PATH)
        except Exception:
            # Fallback: escrever direto (pode causar race condition mas e melhor que nada)
            try:
                with open(DL_PROGRESS_PATH, 'w') as pf:
                    json.dump(prog, pf)
            except:
                pass


def clear_dl_progress(serial):
    """Remove serial do dl_progress.json (thread-safe + atomico)."""
    with _dl_progress_lock:
        try:
            with open(DL_PROGRESS_PATH, 'r') as pf:
                prog = json.load(pf)
        except:
            prog = {}
        prog.pop(serial, None)
        tmp = DL_PROGRESS_PATH + '.tmp'
        try:
            with open(tmp, 'w') as pf:
                json.dump(prog, pf)
            os.replace(tmp, DL_PROGRESS_PATH)
        except Exception:
            try:
                with open(DL_PROGRESS_PATH, 'w') as pf:
                    json.dump(prog, pf)
            except:
                pass

# Cookies do archive.org (conta logada — libera colecoes restritas)
ARCHIVE_COOKIES = {
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
}


def make_session(use_tor=False):
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    s.cookies.update(ARCHIVE_COOKIES)
    if use_tor:
        s.proxies = TOR_PROXY
    return s


def log_error(serial, error_msg, url, use_tor):
    """Registra erro detalhado no log de erros para dashboard."""
    ERROR_LOG_PATH = os.path.join(STATE_DIR, 'download_errors.json')
    errors = {}
    try:
        with open(ERROR_LOG_PATH, 'r', encoding='utf-8') as f:
            errors = json.load(f)
    except:
        pass
    errors[serial] = {
        'error': error_msg,
        'url': url[:200],
        'mode': 'Tor' if use_tor else 'direto',
        'time': time.time(),
        'time_str': time.strftime('%H:%M:%S'),
    }
    try:
        with open(ERROR_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)
    except:
        pass


def download_chunk(url, start, end, dest, chunk_idx, progress, use_tor=False, deadline=None):
    """Baixa uma parte do arquivo usando Range header."""
    for attempt in range(CHUNK_RETRIES):
        # Verificar deadline
        if deadline and time.time() > deadline:
            return False, "timeout global"

        try:
            s = make_session(use_tor)
            headers = {'Range': f'bytes={start}-{end}'}
            r = s.get(url, timeout=(15, 60), stream=True, headers=headers)
            if r.status_code not in (200, 206):
                s.close()
                return False, f"HTTP {r.status_code}"

            offset = start
            with open(dest, 'r+b') as f:
                f.seek(offset)
                for chunk in r.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        f.write(chunk)
                        offset += len(chunk)
                        with progress_lock:
                            progress[chunk_idx] = offset - start
            s.close()

            # Verificar se baixou tudo
            expected = end - start + 1
            with progress_lock:
                actual = progress[chunk_idx]
            if actual >= expected:
                return True, None
            else:
                # Retry - baixar o que falta
                remaining_start = start + actual
                if remaining_start <= end:
                    s2 = make_session(use_tor)
                    headers2 = {'Range': f'bytes={remaining_start}-{end}'}
                    r2 = s2.get(url, timeout=(15, 120), stream=True, headers=headers2)
                    if r2.status_code in (200, 206):
                        with open(dest, 'r+b') as f:
                            f.seek(remaining_start)
                            for chunk in r2.iter_content(chunk_size=256 * 1024):
                                if chunk:
                                    f.write(chunk)
                                    offset += len(chunk)
                                    with progress_lock:
                                        progress[chunk_idx] = offset - start
                    s2.close()
                    with progress_lock:
                        actual = progress[chunk_idx]
                    if actual >= expected:
                        return True, None
        except Exception as e:
            time.sleep(2 * (attempt + 1))
            continue
    return False, f"falha apos {CHUNK_RETRIES} tentativas"


def download_file_parallel(url, dest, total_size, serial, use_tor=False, num_streams=NUM_STREAMS):
    """Baixa arquivo em paralelo usando Range requests."""
    # Pre-alocar arquivo
    with open(dest, 'wb') as f:
        if total_size > 0:
            f.seek(total_size - 1)
            f.write(b'\0')

    # Calcular chunks
    chunk_size = total_size // num_streams
    ranges = []
    for i in range(num_streams):
        start = i * chunk_size
        end = (i + 1) * chunk_size - 1 if i < num_streams - 1 else total_size - 1
        ranges.append((start, end))

    progress = {i: 0 for i in range(num_streams)}
    errors = {i: None for i in range(num_streams)}

    # Deadline: 10 min direto, 8 min Tor (nao ficar preso em Tor lento)
    deadline = time.time() + (480 if use_tor else 600)

    # Lançar threads
    threads = []
    for i, (start, end) in enumerate(ranges):
        t = threading.Thread(
            target=lambda idx=i, s=start, e=end:
                (errors.__setitem__(idx, download_chunk(url, s, e, dest, idx, progress, use_tor, deadline)))
        )
        t.daemon = True
        t.start()
        threads.append(t)

    # Monitorar progresso com deteccao de stall
    t0 = time.time()
    last_update = 0
    last_downloaded = 0
    stall_count = 0
    while any(t.is_alive() for t in threads):
        downloaded = sum(progress.values())
        now = time.time()
        if now - last_update >= 2.0:
            elapsed = now - t0
            speed = downloaded / max(elapsed, 0.1)
            pct = 100 * downloaded / total_size if total_size > 0 else 0
            mode = "Tor" if use_tor else "direto"
            print(f"  {serial} [{mode}]: {downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB ({pct:.0f}%) a {speed/1024:.0f}KB/s", flush=True)
            save_dl_progress(serial, downloaded, total_size, speed)
            # Deteccao de stall: 0 bytes em 30s
            if downloaded == last_downloaded and not use_tor:
                stall_count += 1
                if stall_count >= 15:  # ~30s sem progresso
                    print(f"  {serial}: STALL detectado, abortando direto...", flush=True)
                    deadline = time.time() - 1  # forcar timeout
                    break
            else:
                stall_count = 0
            last_downloaded = downloaded
            last_update = now
        time.sleep(1)

    for t in threads:
        t.join(timeout=300)

    # Verificar chunks incompletos e fazer retry
    for i, (start, end) in enumerate(ranges):
        expected = end - start + 1
        with progress_lock:
            actual = progress[i]
        if actual < expected:
            # Retry do chunk incompleto
            remaining_start = start + actual
            if remaining_start <= end:
                try:
                    s = make_session(use_tor)
                    headers = {'Range': f'bytes={remaining_start}-{end}'}
                    r = s.get(url, timeout=(15, 120), stream=True, headers=headers)
                    if r.status_code in (200, 206):
                        with open(dest, 'r+b') as f:
                            f.seek(remaining_start)
                            for chunk in r.iter_content(chunk_size=256 * 1024):
                                if chunk:
                                    f.write(chunk)
                                    remaining_start += len(chunk)
                                    with progress_lock:
                                        progress[i] = remaining_start - start
                    s.close()
                except:
                    pass

    # Verificar resultado
    final_size = os.path.getsize(dest)
    success = final_size >= total_size * 0.99
    return success, final_size


def download_rom(serial, name, url, expected_size=None, use_tor=False):
    """Baixa um ROM completo.
    Estratégia:
    1. HEAD request para descobrir tamanho e suporte a Range
    2. Se HEAD falhar (403/401), tentar GET com Range: bytes=0-0
    3. Se suportar Range (206), download paralelo
    4. Se não suportar Range (200), download simples
    """
    dest = os.path.join(DOWNLOADS_DIR, f'{serial}.download')

    # Verificar se ja existe
    if os.path.exists(dest):
        existing = os.path.getsize(dest)
        if expected_size and existing >= expected_size * 0.99:
            print(f"  {serial}: ja completo ({existing/1024/1024:.1f}MB)", flush=True)
            return True, existing

    # Tentar descobrir tamanho e suporte a Range
    total = 0
    accept_ranges = 'none'
    error_detail = None

    # Se direto, tentar HTTPS primeiro (archive.org as vezes so responde HTTPS)
    test_url = url
    if not use_tor and url.startswith('http://'):
        test_url_https = url.replace('http://', 'https://', 1)
    else:
        test_url_https = None

    s = make_session(use_tor)
    try:
        # HEAD request
        r = s.head(test_url, timeout=(10, 20), allow_redirects=True)
        if r.status_code in (200, 206):
            total = int(r.headers.get('content-length', 0))
            accept_ranges = r.headers.get('accept-ranges', 'none')
        elif r.status_code in (401, 403):
            # HEAD falhou, tentar GET com Range: bytes=0-0
            s.close()
            s = make_session(use_tor)
            r = s.get(test_url, timeout=(10, 20), stream=True, headers={'Range': 'bytes=0-0'})
            if r.status_code == 206:
                cr = r.headers.get('content-range', '')
                if '/' in cr:
                    total = int(cr.split('/')[-1])
                accept_ranges = 'bytes'
                r.close()
            elif r.status_code == 200:
                total = int(r.headers.get('content-length', 0))
                accept_ranges = 'none'
                r.close()
            else:
                error_detail = f"HTTP {r.status_code} ao acessar arquivo"
                r.close()
        else:
            error_detail = f"HTTP {r.status_code} no HEAD request"
    except requests.exceptions.ConnectTimeout:
        error_detail = "Timeout de conexao (archive.org pode estar fora do ar)"
        # Tentar HTTPS se estavamos usando HTTP
        if test_url_https and not use_tor:
            print(f"  {serial}: HTTP timeout, tentando HTTPS...", flush=True)
            s.close()
            s = make_session(use_tor)
            try:
                r = s.head(test_url_https, timeout=(10, 20), allow_redirects=True)
                if r.status_code in (200, 206):
                    total = int(r.headers.get('content-length', 0))
                    accept_ranges = r.headers.get('accept-ranges', 'none')
                    test_url = test_url_https  # usar HTTPS daqui pra frente
                    error_detail = None
                elif r.status_code in (401, 403):
                    s.close()
                    s = make_session(use_tor)
                    r = s.get(test_url_https, timeout=(10, 20), stream=True, headers={'Range': 'bytes=0-0'})
                    if r.status_code == 206:
                        cr = r.headers.get('content-range', '')
                        if '/' in cr:
                            total = int(cr.split('/')[-1])
                        accept_ranges = 'bytes'
                        test_url = test_url_https
                        error_detail = None
                    elif r.status_code == 200:
                        total = int(r.headers.get('content-length', 0))
                        accept_ranges = 'none'
                        test_url = test_url_https
                        error_detail = None
                    r.close()
                else:
                    error_detail = f"HTTPS tambem falhou: HTTP {r.status_code}"
                r.close()
            except Exception as e2:
                error_detail = f"HTTP e HTTPS ambos falharam: {type(e2).__name__}: {e2}"
    except requests.exceptions.ConnectionError as e:
        error_detail = f"Erro de conexao: {type(e).__name__}: {str(e)[:100]}"
    except Exception as e:
        error_detail = f"Erro inesperado no HEAD: {type(e).__name__}: {str(e)[:100]}"
    finally:
        s.close()

    if total == 0 and expected_size:
        total = expected_size

    if total == 0:
        err = error_detail or "tamanho desconhecido"
        print(f"  {serial}: FALHOU — {err}", flush=True)
        # Log detalhado do erro
        log_error(serial, err, url, use_tor)
        return False, 0

    print(f"  {serial}: {total/1024/1024:.1f}MB, Accept-Ranges={accept_ranges}", flush=True)

    if accept_ranges == 'bytes' and total > 1024 * 1024:  # > 1MB
        # Download paralelo — 16 streams
        num_streams = 16
        success, size = download_file_parallel(test_url, dest, total, serial, use_tor, num_streams)
    else:
        # Download simples (sem Range) — tentar com timeout agressivo
        print(f"  {serial}: download simples (sem Range)", flush=True)
        s = make_session(use_tor)
        try:
            r = s.get(test_url, timeout=(15, 600), stream=True)
            if r.status_code == 200:
                with open(dest, 'wb') as f:
                    dl = 0
                    for chunk in r.iter_content(chunk_size=512 * 1024):
                        if chunk:
                            f.write(chunk)
                            dl += len(chunk)
                success = dl >= total * 0.99
                size = dl
            else:
                err = f"HTTP {r.status_code} no download simples"
                print(f"  {serial}: FALHOU — {err}", flush=True)
                log_error(serial, err, test_url, use_tor)
                success = False
                size = 0
            r.close()
        except requests.exceptions.ConnectTimeout:
            err = "Timeout de conexao no download simples"
            print(f"  {serial}: FALHOU — {err}", flush=True)
            log_error(serial, err, test_url, use_tor)
            success = False
            size = 0
        except requests.exceptions.ReadTimeout:
            err = "Timeout de leitura no download simples (conexao muito lenta)"
            print(f"  {serial}: FALHOU — {err}", flush=True)
            log_error(serial, err, test_url, use_tor)
            success = False
            size = 0
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:100]}"
            print(f"  {serial}: FALHOU — {err}", flush=True)
            log_error(serial, err, test_url, use_tor)
            success = False
            size = 0
        s.close()

    return success, size


_queue_lock = threading.Lock()

def mark_completed(serial, name, site):
    """Marca ROM como completed no queue.json (thread-safe com lock)."""
    with _queue_lock:
        try:
            with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
                q = json.load(f)
        except json.JSONDecodeError:
            # JSON corrompido, tentar reparar
            with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
            depth = 0
            end_pos = 0
            for i, c in enumerate(content):
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        end_pos = i + 1
                        break
            if end_pos > 0:
                q = json.loads(content[:end_pos])
            else:
                return  # nao conseguiu reparar
        q['queue'] = [item for item in q.get('queue', []) if not (isinstance(item, dict) and item.get('serial') == serial)]
        ip = q.get('in_progress', {})
        if isinstance(ip, dict):
            ip.pop(serial, None)
        fl = q.get('failed', {})
        if isinstance(fl, dict):
            fl.pop(serial, None)
        comp = q.get('completed', {})
        if not isinstance(comp, dict):
            comp = {}
        comp[serial] = {'serial': serial, 'name': name, 'site': site, 'completed_at': time.time()}
        q['completed'] = comp
        q['in_progress'] = ip
        q['failed'] = fl
        # Escrever atomicamente: escrever em temp e renomear
        tmp_path = QUEUE_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(q, f, ensure_ascii=False, indent=2)
        try:
            os.replace(tmp_path, QUEUE_PATH)
        except:
            os.rename(tmp_path, QUEUE_PATH)

    # Limpar progresso
    clear_dl_progress(serial)


if __name__ == '__main__':
    # Teste: baixar um arquivo pequeno via Tor paralelo
    test_url = 'http://archive.org/download/psx_momomats/playstationdisc.chd'
    test_dest = os.path.join(DOWNLOADS_DIR, 'TEST_PARALLEL.chd')
    print("Teste: download paralelo via Tor (52MB)", flush=True)
    success, size = download_rom('TEST', 'test', test_url, 52009886, use_tor=True)
    print(f"Resultado: success={success}, size={size/1024/1024:.1f}MB", flush=True)
    if os.path.exists(test_dest):
        os.remove(test_dest)
