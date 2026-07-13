"""Baixa ROMs encontrados pelo deep_archive search."""
import sys, os, time, json
from urllib.parse import quote

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r"D:\roms\library\roms\_importre_state"
DOWNLOADS_DIR = os.path.join(STATE_DIR, "downloads")
QUEUE_PATH = os.path.join(STATE_DIR, "queue.json")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

# Tor session
tor_s = requests.Session()
tor_s.proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
tor_s.headers.update({'User-Agent': 'Mozilla/5.0'})

# Carregar resultados
with open(os.path.join(STATE_DIR, "deep_archive_results.json"), 'r', encoding='utf-8') as f:
    found = json.load(f)

print(f"ROMs encontrados: {len(found)}")

# Pular suspeitos: wakuv (manual) e rr-sony-playstation-j (BIOS)
SKIP_IDENTIFIERS = ['wakuv', 'rr-sony-playstation-j']

for rom in found:
    serial = rom['serial']
    url = rom['url']
    identifier = rom.get('identifier', '')
    filename = rom.get('filename', '')

    if identifier in SKIP_IDENTIFIERS:
        print(f"\n{serial}: pulando {identifier} (suspeito: não é o jogo)")
        continue

    print(f"\n=== {serial} ({identifier}) ===")
    print(f"  URL: {url[:100]}")

    dest = os.path.join(DOWNLOADS_DIR, f"{serial}.download")

    # Tentar direto primeiro
    t0 = time.time()
    try:
        r = s.get(url, timeout=(10, 30), stream=True)
        print(f"  Direto: {r.status_code}")

        if r.status_code == 200:
            total = int(r.headers.get('content-length', 0))
            if total < 1024 * 100:  # < 100KB
                print(f"  Muito pequeno ({total}B), provavelmente HTML")
                r.close()
                continue

            dl = 0
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        dl += len(chunk)
            elapsed = time.time() - t0
            size_mb = dl / 1024 / 1024
            print(f"  OK direto! {size_mb:.1f}MB em {elapsed:.1f}s ({size_mb/elapsed:.1f}MB/s)")

        elif r.status_code in (401, 403):
            print(f"  {r.status_code} — tentando via Tor...")
            r.close()
            r = tor_s.get(url, timeout=(15, 120), stream=True)
            print(f"  Tor: {r.status_code}")

            if r.status_code == 200:
                total = int(r.headers.get('content-length', 0))
                if total < 1024 * 100:
                    print(f"  Muito pequeno via Tor ({total}B)")
                    r.close()
                    continue

                dl = 0
                with open(dest, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=512 * 1024):
                        if chunk:
                            f.write(chunk)
                            dl += len(chunk)
                elapsed = time.time() - t0
                size_mb = dl / 1024 / 1024
                print(f"  OK via Tor! {size_mb:.1f}MB em {elapsed:.1f}s")
            else:
                print(f"  Tor também falhou: {r.status_code}")
                r.close()
                continue
        else:
            print(f"  Falhou: HTTP {r.status_code}")
            r.close()
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
        comp[serial] = {'serial': serial, 'name': rom.get('name', ''), 'site': 'deep_archive', 'completed_at': time.time()}
        q['completed'] = comp
        q['in_progress'] = ip
        q['failed'] = fl
        with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
            json.dump(q, f, ensure_ascii=False, indent=2)
        print(f"  Queue atualizado: {serial} -> completed")

    except Exception as e:
        print(f"  Erro: {e}")

print("\nDone!")
