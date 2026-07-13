"""
Reconstrói índice JP com URLs VÁLIDAS.
Testa cada URL com HEAD request (rápido) antes de adicionar ao índice.
Usa ThreadPoolExecutor para testar em paralelo (50 threads).
"""
import json, os, sys, time
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request, urllib.error

OLD_IDX = r"D:\roms\library\roms\_importre_state\archive_jp_index.json"
NEW_IDX = r"D:\roms\library\roms\_importre_state\archive_jp_valid_index.json"
QUEUE_FILE = r"D:\roms\library\roms\_importre_state\queue.json"

# Carregar índice antigo
old = json.load(open(OLD_IDX, "r", encoding="utf-8"))
print(f"Índice antigo: {len(old)} entradas")

# Carregar fila para ver quais seriais precisamos
q = json.load(open(QUEUE_FILE, "r", encoding="utf-8"))
queue_serials = set()
for item in q.get("queue", []):
    if isinstance(item, dict):
        queue_serials.add(item.get("serial", ""))
completed = q.get("completed", {})
if isinstance(completed, dict):
    done_serials = set(completed.keys())
elif isinstance(completed, list):
    done_serials = set(i.get("serial","") for i in completed if isinstance(i, dict))
else:
    done_serials = set()
needed = queue_serials - done_serials
print(f"Fila: {len(queue_serials)} seriais, {len(needed)} precisam, {len(done_serials)} done")

# Filtrar apenas seriais que precisamos E que estão no índice
to_test = {}
for serial, entry in old.items():
    if serial in needed:
        collection = entry.get("collection", "")
        filename = entry.get("file", "")
        if collection and filename:
            encoded = quote(filename, safe="/")
            url = f"http://archive.org/download/{collection}/{encoded}"
            to_test[serial] = {
                "url": url,
                "collection": collection,
                "filename": filename,
                "size": entry.get("size", 0),
            }
print(f"URLs para testar: {len(to_test)}")

def test_url(serial_entry):
    """Testa URL com HEAD request. Retorna (serial, valid, url, size)."""
    serial, entry = serial_entry
    url = entry["url"]
    try:
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "Mozilla/5.0",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                size = int(resp.headers.get("Content-Length", entry.get("size", 0)))
                return (serial, True, url, size)
            else:
                return (serial, False, url, 0)
    except urllib.error.HTTPError as e:
        return (serial, False, url, 0)
    except Exception as e:
        return (serial, False, url, 0)

# Testar em paralelo
valid = {}
invalid = 0
t0 = time.time()
with ThreadPoolExecutor(max_workers=50) as pool:
    futures = {pool.submit(test_url, (s, e)): s for s, e in to_test.items()}
    done = 0
    for fut in as_completed(futures):
        done += 1
        serial, ok, url, size = fut.result()
        if ok:
            valid[serial] = {
                "download_url": url,
                "filename": to_test[serial]["filename"],
                "size": size,
                "title": to_test[serial]["filename"].rsplit(".", 1)[0],
            }
        else:
            invalid += 1
        if done % 20 == 0:
            elapsed = time.time() - t0
            print(f"  Testadas: {done}/{len(to_test)} | válidas: {len(valid)} | inválidas: {invalid} | {elapsed:.0f}s")

elapsed = time.time() - t0
print(f"\nConcluído em {elapsed:.0f}s:")
print(f"  Válidas: {len(valid)}")
print(f"  Inválidas: {invalid}")

# Salvar índice válido
json.dump(valid, open(NEW_IDX, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Índice válido salvo: {NEW_IDX}")

# Atualizar archive_jp_public_index.json com as URLs válidas
pub_idx_path = r"D:\roms\library\roms\_importre_state\archive_jp_public_index.json"
if os.path.exists(pub_idx_path):
    pub = json.load(open(pub_idx_path, "r", encoding="utf-8"))
else:
    pub = {"serial_index": {}, "name_index": {}}

# Construir serial_index no formato esperado pelo importre
serial_index = {}
for serial, entry in valid.items():
    serial_index[serial] = {
        "identifier": entry["filename"],
        "filename": entry["filename"],
        "download_url": entry["download_url"],
        "title": entry["title"],
        "size": entry["size"],
    }

pub["serial_index"] = serial_index
json.dump(pub, open(pub_idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"archive_jp_public_index.json atualizado: {len(serial_index)} seriais válidos")

# Verificar hits na fila
hits = sum(1 for s in needed if s in valid)
print(f"\nHits na fila: {hits}/{len(needed)} ({hits*100//len(needed) if needed else 0}%)")
