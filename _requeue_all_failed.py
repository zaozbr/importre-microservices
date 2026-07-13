"""Readiciona todos os jogos em _chd_failed a fila do importre para re-download."""
import json
from pathlib import Path

queue_path = Path(r"D:\roms\library\roms\_importre_state\queue.json")
queue_data = json.loads(queue_path.read_text(encoding="utf-8"))

failed_dir = Path(r"D:\roms\library\roms\psx\_chd_failed")

games = {
    "SLPS-02469": "DX Jinsei Game III",
    "SLPM-86014": "Eisei Meijin II",
    "SLPS-02839": "Simple 1500 Jitsuyou Series Vol.04 Ryouri",
    "SLPS-01064": "Battle Master",
    "SLPM-86095": "King of Fighters Kyo",
    "SLPS-03050": "Tales of Eternia Disc 1 of 3",
    "SLPS-00383": "Time Gal & Ninja Hayate",
    "SLES-02272": "Yeh Yeh Tennis",
}

queue_data.setdefault("completed", {})
queue_data.setdefault("failed", {})
queue_data.setdefault("retry_count", {})
queue = queue_data.get("queue", [])

added = 0
for serial, name in games.items():
    for section in ["completed", "failed", "retry_count"]:
        if serial in queue_data[section]:
            del queue_data[section][serial]
    if not any(item.get("serial") == serial for item in queue):
        region = "JP" if serial.startswith("SLPS") or serial.startswith("SLPM") or serial.startswith("PCPX") else "EU"
        queue.append({
            "serial": serial,
            "name": name,
            "region": region,
            "section": "## 🇯🇵 Japão" if region == "JP" else "## 🇪🇺 Europa",
            "type": "commercial",
        })
        added += 1
        print(f"Adicionado: {serial} - {name}")
    else:
        print(f"Ja na fila: {serial} - {name}")

queue_data["queue"] = queue
queue_path.write_text(json.dumps(queue_data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nTotal adicionados: {added}")
print(f"Tamanho da fila: {len(queue)}")
