"""Baixa ROMs encontrados pelo smart_index."""
import requests, time, os, json
from urllib.parse import unquote

STATE_DIR = r"D:\roms\library\roms\_importre_state"
DOWNLOADS_DIR = os.path.join(STATE_DIR, "downloads")
QUEUE_PATH = os.path.join(STATE_DIR, "queue.json")
DL_PROGRESS_PATH = os.path.join(STATE_DIR, "dl_progress.json")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

# Carregar resultados
with open(os.path.join(STATE_DIR, "smart_search_results.json"), 'r', encoding='utf-8') as f:
    results = json.load(f)

found = results.get('found', [])
print(f"ROMs encontrados: {len(found)}")

for rom in found:
    serial = rom['serial']
    url = rom['url']
    filename = rom['filename']
    collection = rom['collection']
    match_type = rom['match_type']
    score = rom['score']

    # Pular SLUS-01527 (psx-roms-archive requer auth)
    if collection == 'psx-roms-archive':
        print(f"\n{serial}: pulando (psx-roms-archive requer auth)")
        continue

    print(f"\n=== {serial} ({match_type}, score={score}) ===")
    print(f"  Collection: {collection}")
    print(f"  Arquivo: {filename}")
    print(f"  URL: {url[:100]}")

    dest = os.path.join(DOWNLOADS_DIR, f"{serial}.download")
    print(f"  Baixando direto...")
    t0 = time.time()
    try:
        r = s.get(url, timeout=(10, 60), stream=True)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            total = int(r.headers.get('content-length', 0))
            dl = 0
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        dl += len(chunk)
            elapsed = time.time() - t0
            size_mb = dl / 1024 / 1024
            print(f"  OK! {size_mb:.1f}MB em {elapsed:.1f}s ({size_mb/elapsed:.1f}MB/s)")

            # Atualizar queue.json
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
            comp[serial] = {'serial': serial, 'name': rom.get('name', ''), 'site': 'smart_index', 'completed_at': time.time()}
            q['completed'] = comp
            q['in_progress'] = ip
            q['failed'] = fl
            with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
                json.dump(q, f, ensure_ascii=False, indent=2)
            print(f"  Queue atualizado: {serial} -> completed")
        elif r.status_code == 401:
            print(f"  401 — requer autenticação")
        elif r.status_code == 403:
            print(f"  403 — proibido (tentar via Tor)")
            # Tentar via Tor
            print(f"  Tentando via Tor...")
            try:
                import sys
                sys.path.insert(0, r"D:\roms\library\roms\psx")
                import importre
                r2 = importre.archive_request("get", url, timeout=(15, 60), stream=True, headers={"User-Agent": "Mozilla/5.0"})
                print(f"  Tor Status: {r2.status_code}")
                if r2.status_code == 200:
                    total = int(r2.headers.get('content-length', 0))
                    dl = 0
                    with open(dest, 'wb') as f:
                        for chunk in r2.iter_content(chunk_size=512 * 1024):
                            if chunk:
                                f.write(chunk)
                                dl += len(chunk)
                    elapsed = time.time() - t0
                    size_mb = dl / 1024 / 1024
                    print(f"  OK via Tor! {size_mb:.1f}MB em {elapsed:.1f}s")
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
                    comp[serial] = {'serial': serial, 'name': rom.get('name', ''), 'site': 'smart_index_tor', 'completed_at': time.time()}
                    q['completed'] = comp
                    q['in_progress'] = ip
                    q['failed'] = fl
                    with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
                        json.dump(q, f, ensure_ascii=False, indent=2)
                    print(f"  Queue atualizado: {serial} -> completed")
            except Exception as e:
                print(f"  Tor falhou: {e}")
        else:
            print(f"  Falhou: HTTP {r.status_code}")
    except Exception as e:
        print(f"  Erro: {e}")

print("\nDone!")
