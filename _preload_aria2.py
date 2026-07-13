"""Pré-popula o aria2c com URLs do índice JP público.
Para cada item na fila que tem serial no índice, adiciona direto ao aria2c."""
import sys, json, os
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _aria2_manager import Aria2Manager

# Carregar índice
idx_path = r"D:\roms\library\roms\_importre_state\archive_jp_public_index.json"
idx = json.load(open(idx_path, "r", encoding="utf-8"))
serial_index = idx.get("serial_index", {})
print(f"Índice: {len(serial_index)} seriais")

# Carregar fila
q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
queue = q.get("queue", [])
completed = q.get("completed", {})
if isinstance(completed, dict):
    completed_serials = set(completed.keys())
elif isinstance(completed, list):
    completed_serials = set(item.get("serial", "") for item in completed if isinstance(item, dict))
else:
    completed_serials = set()

print(f"Fila: {len(queue)} itens, {len(completed_serials)} completados")

# Encontrar itens que podem ser baixados direto do índice
dest_dir = r"D:\roms\library\roms\_importre_state\downloads"
mgr = Aria2Manager()
if not mgr.is_daemon_running():
    print("ERRO: daemon aria2c não está rodando")
    sys.exit(1)

added = 0
skipped = 0
for item in queue:
    if not isinstance(item, dict):
        continue
    serial = item.get("serial", "")
    if serial in completed_serials:
        continue
    if serial in serial_index:
        entry = serial_index[serial]
        url = entry.get("download_url", "")
        filename = entry.get("filename", "")
        if not url or not filename:
            continue
        # Nome do arquivo: serial + nome original
        dest_filename = f"{serial}_{filename}"
        try:
            gid = mgr.add_uri(url, dest_dir=dest_dir, filename=dest_filename)
            added += 1
            if added <= 5:
                print(f"  Adicionado: {serial} -> {url[:80]}")
        except Exception as e:
            skipped += 1
            if skipped <= 3:
                print(f"  Erro: {serial} -> {e}")
    if added >= 50:  # Limitar a 50 downloads simultâneos
        break

print(f"\nTotal: {added} URLs adicionadas ao aria2c, {skipped} erros")

# Status
stat = mgr.get_summary()
print(f"Active: {stat.get('active', 0)}")
print(f"Waiting: {stat.get('waiting', 0)}")
print(f"Speed: {stat.get('download_speed', 0) / 1e6:.2f} MB/s")
