"""
Baixa os 267 ROMs encontrados pelo cross_index.
Estratégia: direto primeiro, Tor paralelo como fallback.
Processa em ordem de tamanho (menores primeiro) para maximizar throughput.
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

# Importar do downloader paralelo
from _tor_parallel_dl import download_rom, mark_completed, DOWNLOADS_DIR, QUEUE_PATH

STATE_DIR = r'D:\roms\library\roms\_importre_state'
RESULTS_PATH = os.path.join(STATE_DIR, 'cross_index_results.json')
LOG_PATH = os.path.join(STATE_DIR, 'mega_download_log.json')


def main():
    print("=" * 70, flush=True)
    print("MEGA DOWNLOAD V2 — baixando 267 ROMs encontrados", flush=True)
    print("=" * 70, flush=True)

    with open(RESULTS_PATH, 'r', encoding='utf-8') as f:
        results = json.load(f)
    found = results.get('found', [])

    # Carregar queue
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    completed = q.get('completed', {})
    if not isinstance(completed, dict):
        completed = {}

    # Carregar log de downloads
    dl_log = {}
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            dl_log = json.load(f)

    # Filtrar ja completados
    to_download = [r for r in found if r['serial'] not in completed and r['serial'] not in dl_log]
    print(f"Para baixar: {len(to_download)}\n", flush=True)

    # Ordenar por tamanho (menores primeiro)
    def get_size(r):
        try:
            return int(r.get('size', '0'))
        except:
            return 0
    to_download.sort(key=get_size)

    # Colecoes restritas (precisam cookies) — Redump.orgSonyPlayStation-* e psx-roms-archive
    # Com cookies do archive.org, todas sao acessiveis via download direto
    RESTRICTED_PREFIXES = ('Redump.orgSonyPlayStation-', 'psx-roms-archive')

    success_count = 0
    fail_count = 0

    for i, rom in enumerate(to_download):
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

        is_restricted = any(collection.startswith(p) for p in RESTRICTED_PREFIXES)

        print(f"\n[{i+1}/{len(to_download)}] {serial} ({name[:30]}) [{collection[:25]}]", flush=True)
        print(f"  Arquivo: {filename[:50]}", flush=True)

        if expected_size and expected_size > 0:
            print(f"  Tamanho: {expected_size/1024/1024:.1f}MB", flush=True)

        success = False

        # Tentar 1: download direto (com cookies — funciona para todas as colecoes)
        try:
            success, size = download_rom(serial, name, url, expected_size, use_tor=False)
        except Exception as e:
            print(f"  Erro direto: {e}", flush=True)

        # Tentar 2: via Tor paralelo (fallback)
        if not success:
            print(f"  Direto falhou, tentando via Tor paralelo...", flush=True)
            dest = os.path.join(DOWNLOADS_DIR, f'{serial}.download')
            if os.path.exists(dest):
                os.remove(dest)
            try:
                success, size = download_rom(serial, name, url, expected_size, use_tor=True)
            except Exception as e:
                print(f"  Erro Tor: {e}", flush=True)

        if success:
            success_count += 1
            site = 'mega_direct' if not success else 'mega_tor'
            mark_completed(serial, name, 'mega_download')
            print(f"  OK! {serial} -> completed", flush=True)
            dl_log[serial] = {'status': 'ok', 'time': time.time()}
        else:
            fail_count += 1
            print(f"  FALHOU: {serial}", flush=True)
            dl_log[serial] = {'status': 'failed', 'time': time.time()}

        # Salvar log
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(dl_log, f, ensure_ascii=False, indent=2)

    print(f"\n=== CONCLUIDO ===", flush=True)
    print(f"Sucesso: {success_count}", flush=True)
    print(f"Falha: {fail_count}", flush=True)

    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    completed = q.get('completed', {})
    if not isinstance(completed, dict):
        completed = {}
    print(f"Total completados no queue: {len(completed)}", flush=True)


if __name__ == '__main__':
    main()
