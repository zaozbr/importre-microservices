"""Verifica índices disponíveis."""
import json, os
idx_path = r"D:\roms\library\roms\_importre_state\archive_jp_index.json"
if os.path.exists(idx_path):
    idx = json.load(open(idx_path, "r", encoding="utf-8"))
    print(f"Indice JP: {len(idx)} entradas")
    # Verificar se tem URL direta
    for k, v in list(idx.items())[:3]:
        print(f"  {k}: {v}")
else:
    print("Indice JP não existe")

# Verificar coolrom_index
cool_path = r"D:\roms\library\roms\_importre_state\coolrom_index.json"
if os.path.exists(cool_path):
    idx = json.load(open(cool_path, "r", encoding="utf-8"))
    print(f"\nIndice CoolROM: {len(idx)} entradas")
else:
    print("\nIndice CoolROM não existe")

# Verificar archive_jp_public_index
pub_path = r"D:\roms\library\roms\_importre_state\archive_jp_public_index.json"
if os.path.exists(pub_path):
    idx = json.load(open(pub_path, "r", encoding="utf-8"))
    si = idx.get("serial_index", {})
    ni = idx.get("name_index", {})
    print(f"\nIndice JP Public: serial={len(si)} name={len(ni)}")
    # Verificar se os seriais da fila estão no índice
    q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
    queue = q.get("queue", [])
    hits = 0
    misses = 0
    for item in queue[:100]:
        if isinstance(item, dict):
            serial = item.get("serial", "")
            if serial in si:
                hits += 1
            else:
                misses += 1
    print(f"  Amostra 100 itens: {hits} hits, {misses} misses")
else:
    print("\nIndice JP Public não existe")
