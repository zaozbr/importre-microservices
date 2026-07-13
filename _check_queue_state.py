"""Verifica estado real da fila e re-enfileira itens presos."""
import json
import os

STATE = r"D:\roms\library\roms\_importre_state"

q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
queue = q.get("queue", [])
completed = q.get("completed", {})
failed = q.get("failed", {})
in_progress = q.get("in_progress", {})

print(f"=== ESTADO DA FILA ===")
print(f"  pending: {len(queue)}")
print(f"  completed: {len(completed)}")
print(f"  failed: {len(failed)}")
print(f"  in_progress: {len(in_progress)}")

# Verificar in_progress — podem estar presos
if isinstance(in_progress, dict):
    print(f"\n=== IN_PROGRESS ({len(in_progress)} itens) ===")
    for serial, info in list(in_progress.items())[:10]:
        print(f"  {serial}: {info}")

# Verificar completed recentes
if isinstance(completed, dict):
    print(f"\n=== COMPLETED ({len(completed)} itens) ===")
    for serial, info in list(completed.items())[:10]:
        if isinstance(info, dict):
            print(f"  {serial}: {info.get('name', '?')[:40]} via {info.get('site', '?')}")
        else:
            print(f"  {serial}: {info}")

# Verificar failed
if isinstance(failed, dict):
    print(f"\n=== FAILED ({len(failed)} itens) ===")
    for serial, info in list(failed.items())[:10]:
        if isinstance(info, dict):
            print(f"  {serial}: {info.get('name', '?')[:40]} — {info.get('reason', '?')[:60]}")
        else:
            print(f"  {serial}: {info}")

# Verificar downloads completados no disco
dl_dir = os.path.join(STATE, "downloads")
if os.path.exists(dl_dir):
    files = [f for f in os.listdir(dl_dir) if not f.endswith(".aria2")]
    total_size = sum(os.path.getsize(os.path.join(dl_dir, f)) for f in files if os.path.isfile(os.path.join(dl_dir, f)))
    print(f"\n=== DOWNLOADS NO DISCO ===")
    print(f"  Arquivos: {len(files)}")
    print(f"  Tamanho: {total_size/1024/1024/1024:.2f}GB")

# Re-enfileirar in_progress presos
if isinstance(in_progress, dict) and len(in_progress) > 0:
    print(f"\n=== RE-ENFILEIRANDO {len(in_progress)} ITENS PRESOS ===")
    for serial, info in in_progress.items():
        name = info.get("name", "") if isinstance(info, dict) else ""
        queue.append({"serial": serial, "name": name})
    q["in_progress"] = {}
    json.dump(q, open(os.path.join(STATE, "queue.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  Re-enfileirados! Nova fila: {len(queue)} pending")
