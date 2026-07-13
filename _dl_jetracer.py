"""Download simples e robusto para SLES-03328 (Jetracer)."""
import requests, time, os, json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r'D:\roms\library\roms\_importre_state'
DOWNLOADS_DIR = os.path.join(STATE_DIR, 'downloads')
QUEUE_PATH = os.path.join(STATE_DIR, 'queue.json')
DL_PROGRESS_PATH = os.path.join(STATE_DIR, 'dl_progress.json')

url = 'http://archive.org/download/jetracer-eu/Jetracer%20%28EU%29.zip'
serial = 'SLES-03328'
dest = os.path.join(DOWNLOADS_DIR, f'{serial}.download')

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

print(f'Baixando {serial}...', flush=True)
t0 = time.time()
r = s.get(url, timeout=(10, 600), stream=True)
print(f'Status: {r.status_code}', flush=True)

if r.status_code == 200:
    total = int(r.headers.get('content-length', 0))
    print(f'Tamanho: {total/1024/1024:.1f}MB', flush=True)

    dl = 0
    last_update = 0
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
            if chunk:
                f.write(chunk)
                dl += len(chunk)
                now = time.time()
                if now - last_update >= 2.0:
                    elapsed = now - t0
                    speed = dl / max(elapsed, 0.1)
                    pct = 100 * dl / total if total > 0 else 0
                    print(f'  {dl/1024/1024:.1f}MB / {total/1024/1024:.1f}MB ({pct:.0f}%) a {speed/1024:.0f}KB/s', flush=True)
                    try:
                        with open(DL_PROGRESS_PATH, 'r') as pf:
                            prog = json.load(pf)
                    except:
                        prog = {}
                    prog[serial] = {'downloaded': dl, 'total': total, 'speed': speed, 'ts': time.time()}
                    with open(DL_PROGRESS_PATH, 'w') as pf:
                        json.dump(prog, pf)
                    last_update = now

    elapsed = time.time() - t0
    print(f'OK! {dl/1024/1024:.1f}MB em {elapsed:.1f}s', flush=True)

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
    comp[serial] = {'serial': serial, 'name': 'JETRACER', 'site': 'direct_download', 'completed_at': time.time()}
    q['completed'] = comp
    q['in_progress'] = ip
    q['failed'] = fl
    with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(q, f, ensure_ascii=False, indent=2)
    print(f'Queue atualizado: {serial} -> completed', flush=True)
else:
    print(f'Falhou: HTTP {r.status_code}', flush=True)
