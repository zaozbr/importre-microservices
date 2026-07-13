"""
EMERGENCIA: Downloader paralelo que baixa 3 ROMs simultaneamente.
Cada ROM usa 16 streams paralelos (Range requests).
Total: 48 conexoes simultaneas com archive.org.

Processa TODOS os ROMs do cross_index que ainda nao foram baixados,
incluindo os que falharam anteriormente.
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

# 3 downloads simultaneos, cada um com 16 streams = 48 conexoes
PARALLEL_DOWNLOADS = 3


def download_one_rom(rom):
    """Baixa um ROM: direto primeiro, Tor paralelo como fallback."""
    serial = rom['serial']
    name = rom.get('name', '')
    url = rom['url']
    collection = rom.get('collection', '')
    filename = rom.get('filename', '')
    expected_size = None
    try:
        expected_size = int(rom.get('size', '0'))
    except:
        pass

    print(f"  [{serial}] {name[:30]} [{collection[:20]}] {filename[:30]}", flush=True)

    # Limpar arquivo parcial anterior
    dest = os.path.join(DOWNLOADS_DIR, f'{serial}.download')
    if os.path.exists(dest):
        existing = os.path.getsize(dest)
        if expected_size and existing >= expected_size * 0.99:
            # Ja completo
            mark_completed(serial, name, 'emergency_download')
            return serial, True, existing
        else:
            os.remove(dest)

    # Tentar 1: download direto (com cookies)
    success = False
    size = 0
    try:
        success, size = download_rom(serial, name, url, expected_size, use_tor=False)
    except Exception as e:
        print(f"  [{serial}] Erro direto: {e}", flush=True)

    # Tentar 2: via Tor paralelo (16 streams)
    if not success:
        print(f"  [{serial}] Direto falhou, Tor paralelo (16 streams)...", flush=True)
        dest = os.path.join(DOWNLOADS_DIR, f'{serial}.download')
        if os.path.exists(dest):
            os.remove(dest)
        try:
            success, size = download_rom(serial, name, url, expected_size, use_tor=True)
        except Exception as e:
            print(f"  [{serial}] Erro Tor: {e}", flush=True)

    if success:
        mark_completed(serial, name, 'emergency_download')
        print(f"  [{serial}] OK! {size/1024/1024:.1f}MB", flush=True)
        return serial, True, size
    else:
        print(f"  [{serial}] FALHOU", flush=True)
        return serial, False, 0


def main():
    print("=" * 70, flush=True)
    print("EMERGENCY DOWNLOAD — 3 ROMs simultaneos x 16 streams = 48 conexoes", flush=True)
    print("=" * 70, flush=True)

    # Carregar resultados do cross_index
    with open(RESULTS_PATH, 'r', encoding='utf-8') as f:
        results = json.load(f)
    found = results.get('found', [])

    # Carregar queue
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    completed = q.get('completed', {})
    if not isinstance(completed, dict):
        completed = {}

    # Carregar log
    dl_log = {}
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            dl_log = json.load(f)

    # Filtrar ja completados e ja processados
    to_download = [r for r in found if r['serial'] not in completed and r['serial'] not in dl_log]
    print(f"Para baixar: {len(to_download)}\n", flush=True)

    # Ordenar por tamanho (menores primeiro para maximizar throughput)
    def get_size(r):
        try:
            return int(r.get('size', '0'))
        except:
            return 0
    to_download.sort(key=get_size)

    success_count = 0
    fail_count = 0

    # Processar em batches de PARALLEL_DOWNLOADS
    for i in range(0, len(to_download), PARALLEL_DOWNLOADS):
        batch = to_download[i:i + PARALLEL_DOWNLOADS]
        print(f"\n=== Batch {i//PARALLEL_DOWNLOADS + 1} ({len(batch)} ROMs) ===", flush=True)

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
                except Exception as e:
                    fail_count += 1
                    dl_log[serial] = {'status': 'error', 'time': time.time(), 'error': str(e)}
                    print(f"  [{serial}] EXCECAO: {e}", flush=True)

        # Salvar log
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(dl_log, f, ensure_ascii=False, indent=2)

        # Status
        with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
            q = json.load(f)
        c = q.get('completed', {})
        if not isinstance(c, dict):
            c = {}
        print(f"  Status: {len(c)} completados, {success_count} ok, {fail_count} falha", flush=True)

    print(f"\n=== CONCLUIDO ===", flush=True)
    print(f"Sucesso: {success_count}", flush=True)
    print(f"Falha: {fail_count}", flush=True)

    # Reprocessar falhas
    failed_roms = [r for r in found if r['serial'] in dl_log and dl_log[r['serial']]['status'] != 'ok' and r['serial'] not in completed]
    if failed_roms:
        print(f"\n=== REPROCESSANDO {len(failed_roms)} FALHAS ===", flush=True)
        for rom in failed_roms:
            serial = rom['serial']
            # Limpar log para retry
            dl_log.pop(serial, None)
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(dl_log, f, ensure_ascii=False, indent=2)

        for i in range(0, len(failed_roms), PARALLEL_DOWNLOADS):
            batch = failed_roms[i:i + PARALLEL_DOWNLOADS]
            print(f"\n=== Retry Batch {i//PARALLEL_DOWNLOADS + 1} ===", flush=True)
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
                            dl_log[s] = {'status': 'failed_retry', 'time': time.time()}
                    except:
                        fail_count += 1
                        dl_log[serial] = {'status': 'error_retry', 'time': time.time()}
            with open(LOG_PATH, 'w', encoding='utf-8') as f:
                json.dump(dl_log, f, ensure_ascii=False, indent=2)

    # Status final
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    c = q.get('completed', {})
    if not isinstance(c, dict):
        c = {}
    print(f"\nTotal completados no queue: {len(c)}", flush=True)


if __name__ == '__main__':
    main()
