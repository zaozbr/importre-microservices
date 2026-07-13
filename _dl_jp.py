"""Baixa ROMs JP encontrados (apenas os legítimos)."""
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
DL_PROGRESS_PATH = os.path.join(STATE_DIR, "dl_progress.json")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

# ROMs legítimos para baixar (identifier -> serial)
TO_DOWNLOAD = [
    {'serial': 'SLPM-86888', 'name': 'MOMOTAROU MATSURI',
     'url': 'http://archive.org/download/psx_momomats/playstationdisc.chd',
     'identifier': 'psx_momomats'},
]

for rom in TO_DOWNLOAD:
    serial = rom['serial']
    url = rom['url']

    # Verificar se já está completed
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    if serial in q.get('completed', {}):
        print(f"{serial}: já completado, pulando")
        continue

    print(f"\n=== {serial} ===")
    print(f"  URL: {url}")

    dest = os.path.join(DOWNLOADS_DIR, f"{serial}.download")
    t0 = time.time()

    # Tentar direto
    try:
        r = s.get(url, timeout=(10, 30), stream=True)
        print(f"  Direto: {r.status_code}")

        if r.status_code == 200:
            total = int(r.headers.get('content-length', 0))
            print(f"  Tamanho: {total/1024/1024:.1f}MB")
            if total < 1024 * 100:
                print(f"  Muito pequeno, pulando")
                r.close()
                continue

            dl = 0
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        dl += len(chunk)
                        # Atualizar progresso
                        elapsed = time.time() - t0
                        speed = dl / max(elapsed, 0.1)
                        try:
                            with open(DL_PROGRESS_PATH, 'r') as pf:
                                prog = json.load(pf)
                        except:
                            prog = {}
                        prog[serial] = {'downloaded': dl, 'total': total, 'speed': speed, 'ts': time.time()}
                        with open(DL_PROGRESS_PATH, 'w') as pf:
                            json.dump(prog, pf)

            elapsed = time.time() - t0
            size_mb = dl / 1024 / 1024
            print(f"  OK! {size_mb:.1f}MB em {elapsed:.1f}s ({size_mb/elapsed:.1f}MB/s)")

            # Limpar progresso
            try:
                with open(DL_PROGRESS_PATH, 'r') as pf:
                    prog = json.load(pf)
                prog.pop(serial, None)
                with open(DL_PROGRESS_PATH, 'w') as pf:
                    json.dump(prog, pf)
            except:
                pass

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
            comp[serial] = {'serial': serial, 'name': rom['name'], 'site': 'jp_search', 'completed_at': time.time()}
            q['completed'] = comp
            q['in_progress'] = ip
            q['failed'] = fl
            with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
                json.dump(q, f, ensure_ascii=False, indent=2)
            print(f"  Queue atualizado: {serial} -> completed")
        else:
            print(f"  Falhou: HTTP {r.status_code}")
    except Exception as e:
        print(f"  Erro: {e}")

print("\nDone!")
