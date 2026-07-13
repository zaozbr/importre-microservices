"""Verifica estado da fila do importre."""
import json
from pathlib import Path

QUEUE_PATH = Path(r"D:\roms\library\roms\_importre_state\queue.json")
data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))

print(f"Pendentes: {len(data.get('queue', []))}")
print(f"Em progresso: {len(data.get('in_progress', {}))}")
print(f"Completados: {len(data.get('completed', {}))}")
print(f"Falhados: {len(data.get('failed', {}))}")

print("\nPrimeiros 10 pendentes:")
for item in data.get("queue", [])[:10]:
    print(f"  {item.get('serial') or 'N/A':15s} {item.get('name', '')}")

print("\nPrimeiros 10 em progresso:")
for serial, item in list(data.get("in_progress", {}).items())[:10]:
    print(f"  {serial:15s} {item.get('name', '')}")
