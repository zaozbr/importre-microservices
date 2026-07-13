"""
Mega Download: baixa ROMs encontrados pelo mega_search.
Tenta download direto primeiro (mais rapido), depois via Tor paralelo se 401/403.
"""
import sys, os, time, json, threading
from urllib.parse import quote

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Importar funcoes do downloader paralelo
from _tor_parallel_dl import download_rom, mark_completed, DOWNLOADS_DIR, QUEUE_PATH

STATE_DIR = r'D:\roms\library\roms\_importre_state'
RESULTS_PATH = os.path.join(STATE_DIR, 'mega_search_results.json')


def main():
    print("=" * 70, flush=True)
    print("MEGA DOWNLOAD — baixando ROMs encontrados", flush=True)
    print("=" * 70, flush=True)

    if not os.path.exists(RESULTS_PATH):
        print("Arquivo de resultados nao encontrado. Rode _mega_search.py primeiro.", flush=True)
        return

    with open(RESULTS_PATH, 'r', encoding='utf-8') as f:
        results = json.load(f)

    found = results.get('found', [])
    print(f"ROMs encontrados: {len(found)}\n", flush=True)

    # Carregar queue para verificar ja completados
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    completed = q.get('completed', {})
    if not isinstance(completed, dict):
        completed = {}

    to_download = [r for r in found if r['serial'] not in completed]
    print(f"Para baixar: {len(to_download)}\n", flush=True)

    for rom in to_download:
        serial = rom['serial']
        name = rom.get('name', '')
        url = rom['url']
        identifier = rom.get('identifier', '')
        filename = rom.get('filename', '')

        # Tentar obter tamanho esperado
        expected_size = None
        try:
            expected_size = int(rom.get('size', '0'))
        except:
            pass

        print(f"\n=== {serial} ({name[:40]}) ===", flush=True)
        print(f"  Identifier: {identifier}", flush=True)
        print(f"  URL: {url[:100]}", flush=True)

        # Tentar 1: download direto (sem Tor) — muito mais rapido
        print(f"  Tentando direto...", flush=True)
        success, size = download_rom(serial, name, url, expected_size, use_tor=False)

        if not success:
            print(f"  Direto falhou, tentando via Tor paralelo...", flush=True)
            # Tentar 2: via Tor paralelo
            # Apagar arquivo parcial
            dest = os.path.join(DOWNLOADS_DIR, f'{serial}.download')
            if os.path.exists(dest):
                os.remove(dest)
            success, size = download_rom(serial, name, url, expected_size, use_tor=True)

        if success:
            print(f"  OK! {size/1024/1024:.1f}MB", flush=True)
            site = 'mega_direct' if not success else 'mega_tor'
            mark_completed(serial, name, site)
            print(f"  Queue atualizado: {serial} -> completed", flush=True)
        else:
            print(f"  FALHOU: {serial}", flush=True)

    print(f"\n=== CONCLUIDO ===", flush=True)
    # Verificar quantos completaram
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    completed = q.get('completed', {})
    if not isinstance(completed, dict):
        completed = {}
    print(f"Total completados: {len(completed)}", flush=True)


if __name__ == '__main__':
    main()
