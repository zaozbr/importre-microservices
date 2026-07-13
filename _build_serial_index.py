"""
Busca em massa no archive.org: para cada serial da fila, busca via API metadata.
Constrói índice de URLs válidas em paralelo (50 threads).
"""
import json, sys, time, re
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request, urllib.error

QUEUE_FILE = r"D:\roms\library\roms\_importre_state\queue.json"
OUT_IDX = r"D:\roms\library\roms\_importre_state\archive_serial_index.json"

# Coleções públicas conhecidas do archive.org com ROMs PSX
COLLECTIONS = [
    "psx-ntscj-chd-zstd",
    "psx-pal-chd-zstd",
    "psx-ntscu-chd-zstd",
    "Redump_PSX_2021_06_04_A_C",
    "Redump_PSX_2021_06_04_D_F",
    "Redump_PSX_2021_06_04_G_I",
    "Redump_PSX_2021_06_04_J_L",
    "Redump_PSX_2021_06_04_M_O",
    "Redump_PSX_2021_06_04_P_R",
    "Redump_PSX_2021_06_04_S_U",
    "Redump_PSX_2021_06_04_V_Z",
    "psx-chd-roms-n",
    "psx-chd-roms-m",
    "CuratedPSXRedumpCHDs",
    "english-psx-isos-and-japanese-translations",
]

ROM_EXTS = {".chd", ".7z", ".zip", ".bin", ".cue", ".iso"}

def fetch_collection_files(identifier):
    """Busca lista de arquivos de um item/coleção do archive.org."""
    url = f"https://archive.org/metadata/{identifier}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            files = data.get("files", [])
            result = []
            for f in files:
                fname = f.get("name", "")
                fext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                if fext in ROM_EXTS:
                    size = int(f.get("size", 0))
                    if size > 1024 * 1024:  # > 1MB
                        result.append({
                            "filename": fname,
                            "size": size,
                            "identifier": identifier,
                        })
            return result
    except:
        return []

# Carregar fila
q = json.load(open(QUEUE_FILE, "r", encoding="utf-8"))
queue_serials = []
for item in q.get("queue", []):
    if isinstance(item, dict):
        s = item.get("serial", "")
        if s:
            queue_serials.append(s)
print(f"Seriais na fila: {len(queue_serials)}")

# Buscar arquivos de todas as coleções em paralelo
print(f"\nBuscando {len(COLLECTIONS)} coleções do archive.org...")
t0 = time.time()
all_files = []
with ThreadPoolExecutor(max_workers=10) as pool:
    futures = {pool.submit(fetch_collection_files, c): c for c in COLLECTIONS}
    for fut in as_completed(futures):
        c = futures[fut]
        files = fut.result()
        all_files.extend(files)
        print(f"  {c}: {len(files)} arquivos")

elapsed = time.time() - t0
print(f"\nTotal: {len(all_files)} arquivos em {elapsed:.0f}s")

# Para cada arquivo, tentar extrair serial do nome
# Padrões: SLUS-XXXXX, SLES-XXXXX, SLPS-XXXXX, SLPM-XXXXX, SCPS-XXXXX, SCES-XXXXX, SCUS-XXXXX
SERIAL_RE = re.compile(r'\b(SL[UP]S|SLPM|SCPS|SCES|SCUS|SLES|SLKA|SIPS|SLEH)-?\s?(\d{4,5})\b', re.IGNORECASE)

serial_to_url = {}
for f in all_files:
    fname = f["filename"]
    m = SERIAL_RE.search(fname)
    if m:
        serial = f"{m.group(1).upper()}-{m.group(2)}"
        encoded = quote(fname, safe="/")
        url = f"http://archive.org/download/{f['identifier']}/{encoded}"
        # Se já existe, preferir o de tamanho maior
        if serial not in serial_to_url or f["size"] > serial_to_url[serial]["size"]:
            serial_to_url[serial] = {
                "download_url": url,
                "filename": fname,
                "size": f["size"],
                "identifier": f["identifier"],
            }

print(f"Seriais extraídos: {len(serial_to_url)}")

# Verificar hits na fila
hits = sum(1 for s in queue_serials if s in serial_to_url)
print(f"Hits na fila: {hits}/{len(queue_serials)} ({hits*100//len(queue_serials) if queue_serials else 0}%)")

# Salvar
json.dump(serial_to_url, open(OUT_IDX, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Índice salvo: {OUT_IDX}")

# Atualizar archive_jp_public_index.json
pub_path = r"D:\roms\library\roms\_importre_state\archive_jp_public_index.json"
pub = json.load(open(pub_path, "r", encoding="utf-8"))
si = {}
for serial, entry in serial_to_url.items():
    si[serial] = {
        "identifier": entry["identifier"],
        "filename": entry["filename"],
        "download_url": entry["download_url"],
        "title": entry["filename"].rsplit(".", 1)[0] if "." in entry["filename"] else entry["filename"],
        "size": entry["size"],
    }
pub["serial_index"] = si
json.dump(pub, open(pub_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"archive_jp_public_index.json atualizado: {len(si)} seriais")
