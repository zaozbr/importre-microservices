"""Diagnostico completo do estado do sistema."""
import json
from pathlib import Path

qpath = Path(r"D:\roms\library\roms\_importre_state\queue.json")
with open(qpath, "r", encoding="utf-8") as f:
    q = json.load(f)

print("=== ESTADO DA FILA ===")
print(f"Pending: {len(q.get('queue', []))}")
print(f"In Progress: {len(q.get('in_progress', {}))}")
completed = q.get("completed", {})
if isinstance(completed, list):
    print(f"Completed: {len(completed)} (lista)")
else:
    print(f"Completed: {len(completed)} (dict)")
failed = q.get("failed", {})
if isinstance(failed, list):
    print(f"Failed: {len(failed)} (lista)")
else:
    print(f"Failed: {len(failed)} (dict)")
print(f"Skipped: {q.get('skipped', 0)}")
print(f"Total: {q.get('total', 0)}")

# Verificar se ha itens skipped
skipped = q.get("skipped", 0)
print(f"\nSkipped field value: {skipped}")

# Listar chaves do queue.json
print(f"\nChaves do queue.json: {list(q.keys())}")

# Verificar sites
spath = Path(r"D:\roms\library\roms\_importre_state\sites.json")
with open(spath, "r", encoding="utf-8") as f:
    sites = json.load(f)
enabled = [k for k, v in sites.items() if v.get("enabled")]
disabled = [k for k, v in sites.items() if not v.get("enabled")]
print(f"\nSites ativos: {len(enabled)} -> {enabled}")
print(f"Sites inativos: {len(disabled)} -> {disabled}")
