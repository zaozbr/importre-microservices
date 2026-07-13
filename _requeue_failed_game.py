"""Readiciona um jogo falhado/corrompido a fila do importre para re-download."""
import json
from pathlib import Path
import time

SERIAL = "SLPS-02469"
NAME = "DX Jinsei Game III"
REGION = "JP"

queue_path = Path(r"D:\roms\library\roms\_importre_state\queue.json")

# Carregar queue.json
queue_data = json.loads(queue_path.read_text(encoding="utf-8"))

# Remover de completed/failed se existir
queue_data.setdefault("completed", {})
queue_data.setdefault("failed", {})
queue_data.setdefault("retry_count", {})

if SERIAL in queue_data["completed"]:
    del queue_data["completed"][SERIAL]
    print(f"Removido de completed: {SERIAL}")
if SERIAL in queue_data["failed"]:
    del queue_data["failed"][SERIAL]
    print(f"Removido de failed: {SERIAL}")
if SERIAL in queue_data["retry_count"]:
    del queue_data["retry_count"][SERIAL]

# Verificar se ja esta na fila
queue = queue_data.get("queue", [])
if any(item.get("serial") == SERIAL for item in queue):
    print(f"{SERIAL} ja esta na fila")
else:
    queue.append({
        "serial": SERIAL,
        "name": NAME,
        "region": REGION,
        "section": "## 🇯🇵 Japão",
        "type": "commercial",
    })
    print(f"{SERIAL} adicionado a fila")

queue_data["queue"] = queue
queue_path.write_text(json.dumps(queue_data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Fila atualizada.")
