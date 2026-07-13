"""Constrói índice público JP a partir do archive_jp_index.json (antigo).
Mapeia serial -> {identifier, filename, download_url} para lookup instantâneo."""
import json, os
from urllib.parse import quote

old_idx_path = r"D:\roms\library\roms\_importre_state\archive_jp_index.json"
new_idx_path = r"D:\roms\library\roms\_importre_state\archive_jp_public_index.json"

# Carregar índice antigo
old_idx = json.load(open(old_idx_path, "r", encoding="utf-8"))
print(f"Índice antigo: {len(old_idx)} entradas")

# Construir serial_index
serial_index = {}
for serial, entry in old_idx.items():
    collection = entry.get("collection", "")
    filename = entry.get("file", "")
    if collection and filename:
        identifier = collection  # identifier = collection no archive.org
        encoded = quote(filename, safe="/")
        download_url = f"http://archive.org/download/{identifier}/{encoded}"
        serial_index[serial] = {
            "identifier": identifier,
            "filename": filename,
            "download_url": download_url,
            "title": filename.rsplit(".", 1)[0] if "." in filename else filename,
            "size": entry.get("size", 0),
        }

print(f"serial_index construído: {len(serial_index)} entradas")

# Carregar índice público existente (preservar name_index)
if os.path.exists(new_idx_path):
    existing = json.load(open(new_idx_path, "r", encoding="utf-8"))
    name_index = existing.get("name_index", {})
    print(f"name_index preservado: {len(name_index)} entradas")
else:
    name_index = {}

# Salvar novo índice
new_idx = {
    "serial_index": serial_index,
    "name_index": name_index,
}
json.dump(new_idx, open(new_idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Índice salvo: {new_idx_path}")
print(f"  serial_index: {len(serial_index)} entradas")
print(f"  name_index: {len(name_index)} entradas")

# Verificar hits na fila
q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
queue = q.get("queue", [])
hits = 0
misses = 0
for item in queue:
    if isinstance(item, dict):
        serial = item.get("serial", "")
        if serial in serial_index:
            hits += 1
        else:
            misses += 1
print(f"\nFila: {hits} hits, {misses} misses de {len(queue)} itens ({hits*100//len(queue) if queue else 0}%)")
