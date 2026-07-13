"""
EMERGENCIA V2: Downloader com deteccao de stall e fallback Tor imediato.
- 3 ROMs simultaneos
- Cada ROM: 16 streams direto, se stall em 20s -> Tor 16 streams
- Reprocessa falhas automaticamente
"""
import sys, os, time, json, threading
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from _tor_parallel_dl import download_rom, mark_completed, DOWNLOADS_DIR, QUEUE_PATH

STATE_DIR = r'D:\roms\library\roms\_importre_state'
RESULTS_PATH = os.path.join(STATE_DIR, 'cross_index_results.json')
LOG_PATH = os.path.join(STATE_DIR, 'emergency_download_log.json')

PARALLEL_DOWNLOADS = 4  # 4 ROMs simultaneos para max throughput
STALL_TIMEOUT = 20  # 20s sem progresso = stall
TOR_STALL_LIMIT = 60  # 60s sem progresso no Tor = abortar e tentar depois


def download_one_rom(rom, force_tor=False):
    """Baixa um ROM: direto primeiro (ou Tor se force_tor), fallback automatico."""
    serial = rom['serial']
    name = rom.get('name', '')
    url = rom['url']
    expected_size = None
    try:
        expected_size = int(rom.get('size', '0'))
    except:
        pass

    dest = os.path.join(DOWNLOADS_DIR, f'{serial}.download')
    if os.path.exists(dest):
        existing = os.path.getsize(dest)
        if expected_size and existing >= expected_size * 0.99:
            mark_completed(serial, name, 'emergency_v2')
            return serial, True, existing
        else:
            try:
                os.remove(dest)
            except:
                pass

    success = False
    size = 0

    # Tentativa 1: direto (ou Tor se force_tor)
    try:
        success, size = download_rom(serial, name, url, expected_size, use_tor=force_tor)
    except Exception as e:
        print(f"  [{serial}] Erro: {e}", flush=True)

    # Tentativa 2: fallback Tor se direto falhou
    if not success and not force_tor:
        print(f"  [{serial}] Direto falhou, Tor paralelo...", flush=True)
        dest = os.path.join(DOWNLOADS_DIR, f'{serial}.download')
        if os.path.exists(dest):
            try:
                os.remove(dest)
            except:
                pass
        try:
            success, size = download_rom(serial, name, url, expected_size, use_tor=True)
        except Exception as e:
            print(f"  [{serial}] Erro Tor: {e}", flush=True)

    if success:
        mark_completed(serial, name, 'emergency_v2')
        print(f"  [{serial}] OK! {size/1024/1024:.1f}MB", flush=True)
        return serial, True, size
    else:
        print(f"  [{serial}] FALHOU", flush=True)
        return serial, False, 0


def main():
    print("=" * 70, flush=True)
    print("EMERGENCY DOWNLOAD V2 — 3x16 streams + fallback Tor", flush=True)
    print("=" * 70, flush=True)

    with open(RESULTS_PATH, 'r', encoding='utf-8') as f:
        results = json.load(f)
    found = results.get('found', [])

    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    completed = q.get('completed', {})
    if not isinstance(completed, dict):
        completed = {}

    dl_log = {}
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            dl_log = json.load(f)

    # Filtrar ja completados
    to_download = [r for r in found if r['serial'] not in completed]
    print(f"Para baixar: {len(to_download)}", flush=True)

    # Ordenar por tamanho (menores primeiro)
    def get_size(r):
        try:
            return int(r.get('size', '0'))
        except:
            return 0
    to_download.sort(key=get_size)

    # Remover do log os que ja estao completed
    dl_log = {k: v for k, v in dl_log.items() if k not in completed}

    success_count = 0
    fail_count = 0
    failed_roms = []

    for i in range(0, len(to_download), PARALLEL_DOWNLOADS):
        batch = to_download[i:i + PARALLEL_DOWNLOADS]
        print(f"\n=== Batch {i//PARALLEL_DOWNLOADS + 1}/{(len(to_download)-1)//PARALLEL_DOWNLOADS + 1} ===", flush=True)

        with ThreadPoolExecutor(max_workers=PARALLEL_DOWNLOADS) as ex:
            futures = {ex.submit(download_one_rom, rom): rom['serial'] for rom in batch}
            for f in as_completed(futures):
                serial = futures[f]
                try:
                    s, success, size = f.result()
                    if success:
                        success_count += 1
                        dl_log[s] = {'status': 'ok', 'time': time.time()}
                    else:
                        fail_count += 1
                        dl_log[s] = {'status': 'failed', 'time': time.time()}
                        failed_roms.append(next((r for r in batch if r['serial'] == s), None))
                except Exception as e:
                    fail_count += 1
                    dl_log[serial] = {'status': 'error', 'time': time.time(), 'error': str(e)}
                    print(f"  [{serial}] EXCECAO: {e}", flush=True)

        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(dl_log, f, ensure_ascii=False, indent=2)

        try:
            with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
                q = json.load(f)
            c = q.get('completed', {})
            if not isinstance(c, dict):
                c = {}
            print(f"  Status: {len(c)} completados, {success_count} ok, {fail_count} falha", flush=True)
        except json.JSONDecodeError:
            print(f"  Status: (JSON corrompido, reparando...) {success_count} ok, {fail_count} falha", flush=True)

    # Reprocessar falhas com Tor forcado
    if failed_roms:
        print(f"\n=== REPROCESSANDO {len(failed_roms)} FALHAS COM TOR ===", flush=True)
        retry_success = 0
        for i in range(0, len(failed_roms), 2):  # 2 paralelos com Tor
            batch = failed_roms[i:i + 2]
            with ThreadPoolExecutor(max_workers=2) as ex:
                futures = {ex.submit(download_one_rom, rom, force_tor=True): rom['serial'] for rom in batch}
                for f in as_completed(futures):
                    serial = futures[f]
                    try:
                        s, success, size = f.result()
                        if success:
                            retry_success += 1
                            dl_log[s] = {'status': 'ok_retry_tor', 'time': time.time()}
                        else:
                            dl_log[s] = {'status': 'failed_retry_tor', 'time': time.time()}
                    except:
                        dl_log[serial] = {'status': 'error_retry_tor', 'time': time.time()}
            with open(LOG_PATH, 'w', encoding='utf-8') as f:
                json.dump(dl_log, f, ensure_ascii=False, indent=2)

        print(f"Retry Tor: {retry_success} recuperados", flush=True)

    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    c = q.get('completed', {})
    if not isinstance(c, dict):
        c = {}
    print(f"\n=== CONCLUIDO: {len(c)} completados ===", flush=True)


if __name__ == '__main__':
    main()
