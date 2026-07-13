"""Re-enfileira in_progress presos e limpa estado para reinicio limpo."""
import json, os

STATE = r"D:\roms\library\roms\_importre_state"

# 1. Re-enfileirar in_progress
q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
ip = q.get("in_progress", {})
print(f"in_progress presos: {len(ip)}")

if isinstance(ip, dict):
    for serial, info in ip.items():
        name = info.get("name", "") if isinstance(info, dict) else ""
        q.setdefault("queue", []).append({"serial": serial, "name": name})
    q["in_progress"] = {}

# 2. Re-enfileirar failed (dar nova chance com cookies)
failed = q.get("failed", {})
print(f"failed re-enfileirando: {len(failed)}")
if isinstance(failed, dict):
    for serial, info in failed.items():
        name = info.get("name", "") if isinstance(info, dict) else ""
        # Só re-enfileirar se não for dos 7 raros conhecidos
        if serial not in ("SLPS-01224", "SLPS-01259", "SLPS-02366", "SLPM-86880", 
                          "SLES-02693", "SLES-01082", "SLPS-02346"):
            q.setdefault("queue", []).append({"serial": serial, "name": name})
    q["failed"] = {}

json.dump(q, open(os.path.join(STATE, "queue.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"\nEstado final:")
print(f"  pending: {len(q.get('queue', []))}")
print(f"  completed: {len(q.get('completed', {}))}")
print(f"  in_progress: {len(q.get('in_progress', {}))}")
print(f"  failed: {len(q.get('failed', {}))}")

# 3. Limpar arquivos de estado
for f in ["aria2_session.txt", "aria2c.log", "dl_progress.json"]:
    p = os.path.join(STATE, f)
    if os.path.exists(p):
        if f.endswith(".json"):
            open(p, "w").write("{}")
        else:
            open(p, "w").close()
        print(f"  Limpou: {f}")
