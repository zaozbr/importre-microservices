"""Baixa SLPS-02427 direto (sem Tor) — psx_tjstomok."""
import requests, time, os, json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r'D:\roms\library\roms\_importre_state'
DOWNLOADS_DIR = os.path.join(STATE_DIR, 'downloads')
QUEUE_PATH = os.path.join(STATE_DIR, 'queue.json')
DL_PROGRESS_PATH = os.path.join(STATE_DIR, 'dl_progress.json')

url = 'http://archive.org/download/psx_tjstomok/playstationdisc.chd'
serial = 'SLPS-02427'
dest = os.path.join(DOWNLOADS_DIR, f'{serial}.download')

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

# Verificar arquivo existente
existing = 0
if os.path.exists(dest):
    existing = os.path.getsize(dest)
    print(f'Arquivo existente: {existing/1024/1024:.1f}MB', flush=True)

print(f'Baixando {serial} direto...', flush=True)
t0 = time.time()

# Se já tem parte, tentar resume com Range
headers = {}
if existing > 0:
    headers['Range'] = f'bytes={existing}-'

r = s.get(url, timeout=(10, 600), stream=True, headers=headers)
print(f'Status: {r.status_code}', flush=True)

if r.status_code in (200, 206):
    total = int(r.headers.get('content-length', 0))
    if r.status_code == 206:
        total += existing  # Range request
        mode = 'ab'
        dl = existing
    else:
        mode = 'wb'
        dl = 0

    print(f'Tamanho total: {total/1024/1024:.1f}MB', flush=True)

    last_update = 0
    with open(dest, mode) as f:
        for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
            if chunk:
                f.write(chunk)
                dl += len(chunk)
                now = time.time()
                if now - last_update >= 2.0:
                    elapsed = now - t0
                    speed = (dl - existing) / max(elapsed, 0.1)
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
    final_size = os.path.getsize(dest)
    print(f'OK! {final_size/1024/1024:.1f}MB em {elapsed:.1f}s', flush=True)

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
    comp[serial] = {'serial': serial, 'name': 'TANTEI JINGUUJI SABURO', 'site': 'direct_download', 'completed_at': time.time()}
    q['completed'] = comp
    q['in_progress'] = ip
    q['failed'] = fl
    with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(q, f, ensure_ascii=False, indent=2)
    print(f'Queue atualizado: {serial} -> completed', flush=True)
else:
    print(f'Falhou: HTTP {r.status_code}', flush=True)
