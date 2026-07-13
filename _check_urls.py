"""Verifica quantos itens na fila têm URL de download já conhecida."""
import json
q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
queue = q.get("queue", [])
with_url = 0
without_url = 0
for item in queue:
    if isinstance(item, dict):
        if item.get("download_url"):
            with_url += 1
        else:
            without_url += 1
print(f"Total na fila: {len(queue)}")
print(f"Com URL de download: {with_url}")
print(f"Sem URL (precisa buscar): {without_url}")

# Verificar in_progress
ip = q.get("in_progress", {})
print(f"\nIn progress: {len(ip)}")
for k, v in list(ip.items())[:10]:
    if isinstance(v, dict):
        url = v.get("download_url", "SEM_URL")
        site = v.get("_current_site", "?")
        phase = v.get("_phase", "?")
        print(f"  {k}: site={site} phase={phase} url={url[:60] if url != 'SEM_URL' else 'SEM_URL'}")
