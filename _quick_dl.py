import requests, time, os, json

url = 'http://archive.org/download/psx-roms-archive/big-league-slugger-baseball-u-slus-01527-.7z'
dest = r'D:\roms\library\roms\_importre_state\downloads\SLUS-01527.download'
print('Baixando SLUS-01527 direto...')
t0 = time.time()
r = requests.get(url, timeout=(10, 60), stream=True, headers={'User-Agent': 'Mozilla/5.0'})
cl = r.headers.get('content-length', '?')
print(f'Status: {r.status_code}, size: {cl} bytes')
if r.status_code == 200:
    total = int(cl) if cl != '?' else 0
    dl = 0
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
            if chunk:
                f.write(chunk)
                dl += len(chunk)
    elapsed = time.time() - t0
    print(f'OK! {dl/1024/1024:.1f}MB em {elapsed:.1f}s ({dl/1024/1024/elapsed:.1f}MB/s)')

    # Atualizar queue.json
    qpath = r'D:\roms\library\roms\_importre_state\queue.json'
    with open(qpath, 'r', encoding='utf-8') as f:
        q = json.load(f)
    # Remover da fila
    q['queue'] = [item for item in q.get('queue', []) if not (isinstance(item, dict) and item.get('serial') == 'SLUS-01527')]
    # Remover de in_progress
    ip = q.get('in_progress', {})
    if isinstance(ip, dict):
        ip.pop('SLUS-01527', None)
    # Remover de failed
    fl = q.get('failed', {})
    if isinstance(fl, dict):
        fl.pop('SLUS-01527', None)
    # Adicionar a completed
    comp = q.get('completed', {})
    if not isinstance(comp, dict):
        comp = {}
    comp['SLUS-01527'] = {'serial': 'SLUS-01527', 'name': 'BIG LEAGUE SLUGGERS BASEBALL', 'site': 'collection_search', 'completed_at': time.time()}
    q['completed'] = comp
    q['in_progress'] = ip
    q['failed'] = fl
    with open(qpath, 'w', encoding='utf-8') as f:
        json.dump(q, f, ensure_ascii=False, indent=2)
    print('Queue atualizado: SLUS-01527 -> completed')
else:
    print(f'Falhou: HTTP {r.status_code}')
