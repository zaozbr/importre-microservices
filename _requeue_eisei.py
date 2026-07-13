"""Readiciona Eisei Meijin II SLPM-86014 a fila do importre."""
import json
from pathlib import Path

queue_path = Path(r"D:\roms\library\roms\_importre_state\queue.json")
queue_data = json.loads(queue_path.read_text(encoding="utf-8"))

serial = "SLPM-86014"
name = "Eisei Meijin II"
region = "JP"

queue_data.setdefault("completed", {})
queue_data.setdefault("failed", {})
queue_data.setdefault("retry_count", {})

for section in ["completed", "failed", "retry_count"]:
    if serial in queue_data[section]:
        del queue_data[section][serial]
        print(f"Removido de {section}: {serial}")

queue = queue_data.get("queue", [])
if not any(item.get("serial") == serial for item in queue):
    queue.append({
        "serial": serial,
        "name": name,
        "region": region,
        "section": "## 🇯🇵 Japão",
        "type": "commercial",
    })
    print(f"{serial} adicionado a fila")
else:
    print(f"{serial} ja esta na fila")

queue_data["queue"] = queue
queue_path.write_text(json.dumps(queue_data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Fila atualizada.")
