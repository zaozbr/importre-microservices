"""Verifica estado do queue.json em detalhe."""
import json, os, time

qpath = r"D:\roms\library\roms\_importre_state\queue.json"
q = json.load(open(qpath, "r", encoding="utf-8"))

print(f"pending={len(q.get('queue',[]))}")
print(f"in_progress={len(q.get('in_progress',{}))}")
print(f"completed={len(q.get('completed',{}))}")
print(f"failed={len(q.get('failed',{}))}")

# Mostrar in_progress
ip = q.get("in_progress", {})
if ip:
    print("\nIn progress:")
    for k, v in list(ip.items())[:5]:
        print(f"  {k}: {v}")
else:
    print("\nIn progress: VAZIO!")

# Verificar dl_progress
dlp = r"D:\roms\library\roms\_importre_state\dl_progress.json"
if os.path.exists(dlp):
    d = json.load(open(dlp, "r", encoding="utf-8"))
    print(f"\ndl_progress: {len(d)} itens")
    for k, v in list(d.items())[:5]:
        print(f"  {k}: {v}")

# Verificar se o arquivo foi modificado recentemente
age = int(time.time() - os.path.getmtime(qpath))
print(f"\nqueue.json age: {age}s")
