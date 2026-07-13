"""
Constrói índice serial->URL cruzando nomes de jogos da fila com arquivos do archive.org.
Estratégia: para cada item na fila, buscar arquivo com nome correspondente nas coleções.
"""
import json, sys, time, re, os
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

QUEUE_FILE = r"D:\roms\library\roms\_importre_state\queue.json"
OUT_IDX = r"D:\roms\library\roms\_importre_state\archive_name_index.json"

COLLECTIONS = {
    "psx-ntscj-chd-zstd": "ntscj/",
    "psx-pal-chd-zstd": "pal/",
    "psx-ntscu-chd-zstd": "ntscu/",
    "psx-chd-roms-n": "",
    "psx-chd-roms-m": "",
    "CuratedPSXRedumpCHDs": "",
    "Redump_PSX_2021_06_04_A_C": "",
    "Redump_PSX_2021_06_04_D_F": "",
    "english-psx-isos-and-japanese-translations": "",
}

ROM_EXTS = {".chd", ".7z", ".zip"}

def fetch_files(identifier):
    """Busca lista de arquivos ROM de uma coleção."""
    url = f"https://archive.org/metadata/{identifier}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            files = data.get("files", [])
            result = []
            for f in files:
                fname = f.get("name", "")
                fext = "." + fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                if fext in ROM_EXTS:
                    size = int(f.get("size", 0))
                    if size > 1024 * 1024:
                        result.append({"filename": fname, "size": size, "identifier": identifier})
            return result
    except:
        return []

def normalize_name(name):
    """Normaliza nome para matching: remove (parens), pontuação, lowercase."""
    # Remover (Japan), (Europe), etc.
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'\[[^\]]*\]', '', name)
    # Remover pontuação e normalizar
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

# Carregar fila
q = json.load(open(QUEUE_FILE, "r", encoding="utf-8"))
queue = q.get("queue", [])
completed = q.get("completed", {})
if isinstance(completed, dict):
    done_serials = set(completed.keys())
elif isinstance(completed, list):
    done_serials = set(i.get("serial","") for i in completed if isinstance(i, dict))
else:
    done_serials = set()

# Construir dict serial -> nome normalizado
serial_to_name = {}
for item in queue:
    if isinstance(item, dict):
        serial = item.get("serial", "")
        name = item.get("name", "")
        if serial and serial not in done_serials and name:
            serial_to_name[serial] = {
                "name": name,
                "name_norm": normalize_name(name),
            }
print(f"Seriais na fila com nome: {len(serial_to_name)}")

# Buscar arquivos de todas as coleções
print(f"\nBuscando {len(COLLECTIONS)} coleções...")
t0 = time.time()
all_files = []
with ThreadPoolExecutor(max_workers=10) as pool:
    futures = {pool.submit(fetch_files, c): c for c in COLLECTIONS}
    for fut in as_completed(futures):
        c = futures[fut]
        files = fut.result()
        all_files.extend(files)
        print(f"  {c}: {len(files)} arquivos")
elapsed = time.time() - t0
print(f"Total: {len(all_files)} arquivos em {elapsed:.0f}s")

# Construir índice nome_normalizado -> arquivo
name_to_file = {}
for f in all_files:
    fname = f["filename"]
    # Remover path prefix e extensão
    base = fname.split("/")[-1] if "/" in fname else fname
    base_no_ext = base.rsplit(".", 1)[0] if "." in base else base
    norm = normalize_name(base_no_ext)
    if norm not in name_to_file or f["size"] > name_to_file[norm]["size"]:
        name_to_file[norm] = f

print(f"Nomes únicos de arquivos: {len(name_to_file)}")

# Matching: para cada serial na fila, procurar nome correspondente
matches = {}
no_match = []
for serial, info in serial_to_name.items():
    name_norm = info["name_norm"]
    if name_norm in name_to_file:
        f = name_to_file[name_norm]
        encoded = quote(f["filename"], safe="/")
        url = f"http://archive.org/download/{f['identifier']}/{encoded}"
        matches[serial] = {
            "download_url": url,
            "filename": f["filename"],
            "size": f["size"],
            "identifier": f["identifier"],
            "name": info["name"],
        }

# Matching parcial: se nome exato não bate, tentar palavras-chave
if len(matches) < len(serial_to_name) * 0.5:
    print(f"\nMatching exato: {len(matches)} — tentando matching parcial...")
    for serial, info in serial_to_name.items():
        if serial in matches:
            continue
        name_norm = info["name_norm"]
        # Pegar palavras significativas (>3 chars)
        words = [w for w in name_norm.split() if len(w) > 3]
        if not words:
            no_match.append(serial)
            continue
        # Procurar arquivo que contenha todas as palavras
        best_match = None
        best_score = 0
        for norm, f in name_to_file.items():
            score = sum(1 for w in words if w in norm)
            if score > best_score:
                best_score = score
                best_match = (norm, f)
        # Aceitar se >= 80% das palavras batem
        if best_match and best_score >= max(2, len(words) * 4 // 5):
            norm, f = best_match
            encoded = quote(f["filename"], safe="/")
            url = f"http://archive.org/download/{f['identifier']}/{encoded}"
            matches[serial] = {
                "download_url": url,
                "filename": f["filename"],
                "size": f["size"],
                "identifier": f["identifier"],
                "name": info["name"],
                "match_score": best_score,
                "match_type": "partial",
            }

print(f"\nResultados:")
print(f"  Matches: {len(matches)}")
print(f"  No match: {len(serial_to_name) - len(matches)}")
print(f"  Hit rate: {len(matches)*100//len(serial_to_name) if serial_to_name else 0}%")

# Salvar
json.dump(matches, open(OUT_IDX, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\nÍndice salvo: {OUT_IDX}")

# Atualizar archive_jp_public_index.json
pub_path = r"D:\roms\library\roms\_importre_state\archive_jp_public_index.json"
pub = json.load(open(pub_path, "r", encoding="utf-8"))
si = {}
for serial, entry in matches.items():
    si[serial] = {
        "identifier": entry["identifier"],
        "filename": entry["filename"],
        "download_url": entry["download_url"],
        "title": entry["name"],
        "size": entry["size"],
    }
pub["serial_index"] = si
json.dump(pub, open(pub_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"archive_jp_public_index.json atualizado: {len(si)} seriais")

# Mostrar alguns matches
print("\nAmostra de matches:")
for serial, entry in list(matches.items())[:5]:
    print(f"  {serial}: {entry['name'][:40]} -> {entry['filename'][:60]}")
