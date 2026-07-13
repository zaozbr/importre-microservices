"""Baixa ROMs direto do archive.org (sem Tor) — muito mais rápido."""
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

# ROMs para baixar direto (todos HTTP 200 confirmado)
ROMS = [
    {'serial': 'SLPM-86888', 'name': 'MOMOTAROU MATSURI',
     'url': 'http://archive.org/download/psx_momomats/playstationdisc.chd',
     'total_expected': 52009886},
    {'serial': 'SLES-03328', 'name': 'JETRACER',
     'url': 'http://archive.org/download/jetracer-eu/Jetracer%20%28EU%29.zip',
     'total_expected': 243492521},
]

for rom in ROMS:
    serial = rom['serial']
    url = rom['url']

    # Verificar se já está completed
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)
    if serial in q.get('completed', {}):
        print(f"{serial}: já completado, pulando", flush=True)
        continue

    # Verificar se já existe arquivo .download com tamanho correto
    dest = os.path.join(DOWNLOADS_DIR, f"{serial}.download")
    if os.path.exists(dest):
        existing_size = os.path.getsize(dest)
        if existing_size >= rom['total_expected']:
            print(f"{serial}: arquivo já existe ({existing_size/1024/1024:.1f}MB), marcando como completo", flush=True)
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
            comp[serial] = {'serial': serial, 'name': rom['name'], 'site': 'direct_download', 'completed_at': time.time()}
            q['completed'] = comp
            q['in_progress'] = ip
            q['failed'] = fl
            with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
                json.dump(q, f, ensure_ascii=False, indent=2)
            print(f"  Queue atualizado: {serial} -> completed", flush=True)
            continue
        else:
            print(f"{serial}: arquivo parcial ({existing_size/1024/1024:.1f}MB), re-baixando", flush=True)

    print(f"\n=== {serial} ({rom['name']}) ===", flush=True)
    print(f"  URL: {url}", flush=True)
    print(f"  Tamanho esperado: {rom['total_expected']/1024/1024:.1f}MB", flush=True)

    t0 = time.time()
    try:
        r = s.get(url, timeout=(10, 60), stream=True)
        print(f"  Status: {r.status_code}", flush=True)

        if r.status_code == 200:
            total = int(r.headers.get('content-length', 0))
            print(f"  Content-Length: {total/1024/1024:.1f}MB", flush=True)

            dl = 0
            last_update = 0
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        dl += len(chunk)
                        now = time.time()
                        if now - last_update >= 1.0:
                            elapsed = now - t0
                            speed = dl / max(elapsed, 0.1)
                            print(f"  {dl/1024/1024:.1f}MB / {total/1024/1024:.1f}MB ({100*dl/total:.0f}%) a {speed/1024:.0f}KB/s", flush=True)
                            # Atualizar progresso
                            try:
                                with open(DL_PROGRESS_PATH, 'r') as pf:
                                    prog = json.load(pf)
                            except:
                                prog = {}
                            prog[serial] = {'downloaded': dl, 'total': total, 'speed': speed, 'ts': time.time()}
                            try:
                                with open(DL_PROGRESS_PATH, 'w') as pf:
                                    json.dump(prog, pf)
                            except:
                                pass
                            last_update = now

            elapsed = time.time() - t0
            size_mb = dl / 1024 / 1024
            print(f"  OK! {size_mb:.1f}MB em {elapsed:.1f}s ({size_mb/elapsed:.1f}MB/s)", flush=True)

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
            comp[serial] = {'serial': serial, 'name': rom['name'], 'site': 'direct_download', 'completed_at': time.time()}
            q['completed'] = comp
            q['in_progress'] = ip
            q['failed'] = fl
            with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
                json.dump(q, f, ensure_ascii=False, indent=2)
            print(f"  Queue atualizado: {serial} -> completed", flush=True)
        else:
            print(f"  Falhou: HTTP {r.status_code}", flush=True)
    except Exception as e:
        print(f"  Erro: {e}", flush=True)

print("\nDone!", flush=True)
