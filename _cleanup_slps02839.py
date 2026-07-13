"""Move bin corrompido de SLPS-02839 para falhas e readiciona a fila."""
import json
from pathlib import Path
import shutil

psx = Path(r"D:\roms\library\roms\psx")
failed_dir = psx / "_chd_failed"
failed_dir.mkdir(exist_ok=True)

serial = "SLPS-02839"
bin_file = psx / "Simple-1500-Jitsuyou-Series-Vol.04-Ryouri-SLPS-02839.bin"
if bin_file.exists():
    dst = failed_dir / bin_file.name
    if dst.exists():
        dst.unlink()
    shutil.move(str(bin_file), str(dst))
    print(f"Movido para falhas: {bin_file.name}")

# Remover CUE para evitar nova tentativa
for name in ["Simple-1500-Jitsuyou-Series-Vol.04-Ryouri-SLPS-02839.cue"]:
    f = psx / name
    if f.exists():
        f.unlink()
        print(f"Removido: {f.name}")

# Adicionar a fila do importre
queue_path = Path(r"D:\roms\library\roms\_importre_state\queue.json")
queue_data = json.loads(queue_path.read_text(encoding="utf-8"))
queue_data.setdefault("completed", {})
queue_data.setdefault("failed", {})
queue_data.setdefault("retry_count", {})
for section in ["completed", "failed", "retry_count"]:
    if serial in queue_data[section]:
        del queue_data[section][serial]

queue = queue_data.get("queue", [])
if not any(item.get("serial") == serial for item in queue):
    queue.append({
        "serial": serial,
        "name": "Simple 1500 Jitsuyou Series Vol.04 Ryouri",
        "region": "JP",
        "section": "## 🇯🇵 Japão",
        "type": "commercial",
    })
    print(f"{serial} adicionado a fila")

queue_data["queue"] = queue
queue_path.write_text(json.dumps(queue_data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Concluido.")
