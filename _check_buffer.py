"""Verifica se o buffer esta sendo usado e se os seriais coincidem com a fila."""
import json
import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")

import importre

# Carregar buffer
buf = importre.buffer_load()
print(f"Buffer: {len(buf)} itens")
for serial, entry in list(buf.items())[:10]:
    if isinstance(entry, tuple):
        t, url, site, detail = entry
        print(f"  {serial}: type={t} site={site} url={str(url)[:80]}")
    elif isinstance(entry, dict):
        print(f"  {serial}: {entry.get('type','')} site={entry.get('site','')} url={str(entry.get('url',''))[:80]}")
    else:
        print(f"  {serial}: {entry}")

# Carregar fila
qpath = r"D:\roms\library\roms\_importre_state\queue.json"
with open(qpath, "r", encoding="utf-8") as f:
    q = json.load(f)

queue = q.get("queue", [])
in_prog = q.get("in_progress", {})

# Verificar quantos itens da fila estao no buffer
buf_serials = set(buf.keys())
queue_in_buf = 0
for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else ""
    if serial in buf_serials:
        queue_in_buf += 1

ip_in_buf = 0
for serial in in_prog:
    if serial in buf_serials:
        ip_in_buf += 1

print(f"\nItens da fila no buffer: {queue_in_buf}/{len(queue)}")
print(f"Itens em progresso no buffer: {ip_in_buf}/{len(in_prog)}")

# Verificar se algum item em progresso tem _needs_search
needs_search = 0
has_url = 0
for serial, item in in_prog.items():
    if item.get("_needs_search"):
        needs_search += 1
    if not item.get("_needs_search"):
        has_url += 1

print(f"\nIn progress com _needs_search=True: {needs_search}")
print(f"In progress com _needs_search=False: {has_url}")
