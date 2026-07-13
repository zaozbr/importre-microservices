"""Re-enfileira itens falhados (timeout de archive.org nao e falha real)."""
import json
from pathlib import Path

qpath = Path(r"D:\roms\library\roms\_importre_state\queue.json")
with open(qpath, "r", encoding="utf-8") as f:
    q = json.load(f)

failed = q.get("failed", {})
queue = q.get("queue", [])
requeued = 0
for serial, info in failed.items():
    if isinstance(info, dict):
        reason = info.get("reason", info.get("failed_at", ""))
    else:
        reason = str(info)
    # Re-enfileirar se for timeout/erro de conexao
    if any(x in reason.lower() for x in ["timeout", "connect", "max retries", "connection", "erro: download", "nenhuma url", "todos os sites falharam"]):
        item = {"serial": serial, "name": info.get("name", "") if isinstance(info, dict) else ""}
        queue.append(item)
        requeued += 1

# Remover os re-enfileirados do failed
if isinstance(failed, dict):
    new_failed = {}
    for serial, info in failed.items():
        if isinstance(info, dict):
            reason = info.get("reason", info.get("failed_at", ""))
        else:
            reason = str(info)
        if not any(x in reason.lower() for x in ["timeout", "connect", "max retries", "connection", "erro: download", "nenhuma url", "todos os sites falharam"]):
            new_failed[serial] = info
    q["failed"] = new_failed
else:
    q["failed"] = failed

q["queue"] = queue
with open(qpath, "w", encoding="utf-8") as f:
    json.dump(q, f, indent=2, ensure_ascii=False)

print(f"Re-enfileirados: {requeued}")
print(f"Falhos restantes: {len(q['failed'])}")
print(f"Pendentes: {len(queue)}")
