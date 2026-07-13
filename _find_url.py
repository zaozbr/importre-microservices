"""Encontrar URLs válidas para teste."""
import json
q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
# Procurar itens com download_url
for key, item in q.get("in_progress", {}).items():
    url = item.get("download_url", "")
    if url and "archive.org" in url:
        print(f"{key}: {url}")
        break

# Procurar itens completed com URL conhecida
completed = q.get("completed", {})
if isinstance(completed, dict):
    items = list(completed.values())[-5:]
elif isinstance(completed, list):
    items = completed[-5:]
else:
    items = []
for item in items:
    if isinstance(item, dict) and item.get("download_url"):
        print(f"completed: {item.get('serial')} -> {item.get('download_url')}")
