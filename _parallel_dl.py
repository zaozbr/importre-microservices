"""Downloader paralelo usando Range requests — múltiplas conexões para acelerar."""
import sys, os, time, json, threading
from urllib.parse import quote

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r"D:\roms\library\roms\_importre_state"
DOWNLOADS_DIR = os.path.join(STATE_DIR, "downloads")
QUEUE_PATH = os.path.join(STATE_DIR, "queue.json")
DL_PROGRESS_PATH = os.path.join(STATE_DIR, "dl_progress.json")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

NUM_CHUNKS = 8  # 8 conexões paralelas
progress_lock = threading.Lock()


def download_chunk(url, start, end, dest, chunk_idx, progress):
    """Baixa uma parte do arquivo usando Range header."""
    headers = {'Range': f'bytes={start}-{end}'}
    try:
        r = s.get(url, timeout=(10, 120), stream=True, headers=headers)
        if r.status_code not in (200, 206):
            return False, f"HTTP {r.status_code}"

        offset = start
        with open(dest, 'r+b') as f:
            f.seek(offset)
            for chunk in r.iter_content(chunk_size=512 * 1024):
                if chunk:
                    f.write(chunk)
                    offset += len(chunk)
                    with progress_lock:
                        progress[chunk_idx] = offset - start
        return True, None
    except Exception as e:
        return False, str(e)[:100]


def download_parallel(url, dest, total_size, serial):
    """Baixa arquivo em paralelo usando Range requests."""
    # Pré-alocar arquivo
    with open(dest, 'wb') as f:
        f.seek(total_size - 1)
        f.write(b'\0')

    # Calcular chunks
    chunk_size = total_size // NUM_CHUNKS
    ranges = []
    for i in range(NUM_CHUNKS):
        start = i * chunk_size
        end = (i + 1) * chunk_size - 1 if i < NUM_CHUNKS - 1 else total_size - 1
        ranges.append((start, end))

    progress = {i: 0 for i in range(NUM_CHUNKS)}
    threads = []
    for i, (start, end) in enumerate(ranges):
        t = threading.Thread(target=download_chunk, args=(url, start, end, dest, i, progress))
        t.start()
        threads.append(t)

    # Monitorar progresso
    t0 = time.time()
    while any(t.is_alive() for t in threads):
        downloaded = sum(progress.values())
        elapsed = time.time() - t0
        speed = downloaded / max(elapsed, 0.1)
        pct = 100 * downloaded / total_size if total_size > 0 else 0
        print(f"  {serial}: {downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB ({pct:.0f}%) a {speed/1024:.0f}KB/s", flush=True)

        # Atualizar dl_progress
        try:
            with open(DL_PROGRESS_PATH, 'r') as pf:
                prog = json.load(pf)
        except:
            prog = {}
        prog[serial] = {'downloaded': downloaded, 'total': total_size, 'speed': speed, 'ts': time.time()}
        try:
            with open(DL_PROGRESS_PATH, 'w') as pf:
                json.dump(prog, pf)
        except:
            pass

        time.sleep(2)

    # Aguardar todas threads
    for t in threads:
        t.join(timeout=300)

    # Verificar tamanho final
    final_size = os.path.getsize(dest)
    return final_size == total_size, final_size


def main():
    # ROMs para baixar com conexões paralelas
    ROMS = [
        {'serial': 'SLES-03328', 'name': 'JETRACER',
         'url': 'http://archive.org/download/jetracer-eu/Jetracer%20%28EU%29.zip',
         'total_expected': 243492521},
    ]

    for rom in ROMS:
        serial = rom['serial']
        url = rom['url']
        total = rom['total_expected']

        # Verificar se já está completed
        with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
            q = json.load(f)
        if serial in q.get('completed', {}):
            print(f"{serial}: já completado, pulando", flush=True)
            continue

        # Verificar arquivo existente
        dest = os.path.join(DOWNLOADS_DIR, f"{serial}.download")
        if os.path.exists(dest) and os.path.getsize(dest) >= total:
            print(f"{serial}: arquivo já completo", flush=True)
        else:
            print(f"\n=== {serial} ({rom['name']}) ===", flush=True)
            print(f"  URL: {url}", flush=True)
            print(f"  Tamanho: {total/1024/1024:.1f}MB", flush=True)
            print(f"  Conexões paralelas: {NUM_CHUNKS}", flush=True)

            # Verificar se servidor suporta Range
            r = s.head(url, timeout=10)
            accept_ranges = r.headers.get('Accept-Ranges', 'none')
            print(f"  Accept-Ranges: {accept_ranges}", flush=True)

            if accept_ranges == 'bytes':
                success, size = download_parallel(url, dest, total, serial)
            else:
                # Fallback: download simples
                print(f"  Servidor não suporta Range, download simples...", flush=True)
                r = s.get(url, timeout=(10, 300), stream=True)
                with open(dest, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                        if chunk:
                            f.write(chunk)
                success = os.path.getsize(dest) == total
                size = os.path.getsize(dest)

            if success:
                print(f"  OK! {size/1024/1024:.1f}MB", flush=True)
            else:
                print(f"  Tamanho incorreto: {size} vs {total}", flush=True)
                continue

        # Atualizar queue
        with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
            q = json.load(f)
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
        comp[serial] = {'serial': serial, 'name': rom['name'], 'site': 'parallel_download', 'completed_at': time.time()}
        q['completed'] = comp
        q['in_progress'] = ip
        q['failed'] = fl
        with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
            json.dump(q, f, ensure_ascii=False, indent=2)
        print(f"  Queue atualizado: {serial} -> completed", flush=True)

        # Limpar progresso
        try:
            with open(DL_PROGRESS_PATH, 'r') as pf:
                prog = json.load(pf)
            prog.pop(serial, None)
            with open(DL_PROGRESS_PATH, 'w') as pf:
                json.dump(prog, pf)
        except:
            pass

    print("\nDone!", flush=True)


if __name__ == '__main__':
    main()
