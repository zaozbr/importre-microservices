"""Tenta baixar ROMs das collections access-restricted via Tor."""
import sys, os, time, json
from urllib.parse import quote

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r"D:\roms\library\roms\_importre_state"

# Tor session
tor_s = requests.Session()
tor_s.proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
tor_s.headers.update({'User-Agent': 'Mozilla/5.0'})

# Carregar resultados do smart_index
with open(os.path.join(STATE_DIR, "smart_search_results.json"), 'r', encoding='utf-8') as f:
    results = json.load(f)

found = results.get('found', [])
print(f"ROMs encontrados pelo smart_index: {len(found)}")

for rom in found:
    serial = rom['serial']
    url = rom['url']
    collection = rom['collection']
    filename = rom['filename']

    # Só tentar collections access-restricted
    if collection not in ('psx-roms-archive', 'Redump.orgSonyPlayStation-PAL-J',
                          'Redump.orgSonyPlayStation-NTSC-U-S', 'Redump.orgSonyPlayStation-NTSC-U-B'):
        print(f"\n{serial}: {collection} já é acessível, pulando")
        continue

    print(f"\n=== {serial} via Tor ===")
    print(f"  URL: {url[:80]}")

    dest = os.path.join(STATE_DIR, "downloads", f"{serial}.download")
    t0 = time.time()
    try:
        r = tor_s.get(url, timeout=(15, 120), stream=True)
        print(f"  Tor Status: {r.status_code}")
        if r.status_code == 200:
            total = int(r.headers.get('content-length', 0))
            dl = 0
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=512 * 1024):
                    if chunk:
                        f.write(chunk)
                        dl += len(chunk)
            elapsed = time.time() - t0
            size_mb = dl / 1024 / 1024
            print(f"  OK via Tor! {size_mb:.1f}MB em {elapsed:.1f}s")

            # Atualizar queue
            qpath = os.path.join(STATE_DIR, "queue.json")
            with open(qpath, 'r', encoding='utf-8') as f:
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
            comp[serial] = {'serial': serial, 'name': rom.get('name', ''), 'site': 'smart_index_tor', 'completed_at': time.time()}
            q['completed'] = comp
            q['in_progress'] = ip
            q['failed'] = fl
            with open(qpath, 'w', encoding='utf-8') as f:
                json.dump(q, f, ensure_ascii=False, indent=2)
            print(f"  Queue atualizado: {serial} -> completed")
        else:
            print(f"  Tor também falhou: HTTP {r.status_code}")
    except Exception as e:
        print(f"  Tor erro: {e}")

print("\nDone!")
