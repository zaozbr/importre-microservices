import json, os
with open(r"D:\roms\library\roms\_importre_state\queue.json", "r") as f:
    q = json.load(f)
ip = q.get("in_progress", {})
print(f"in_progress: {len(ip)} itens")
for k in list(ip.keys())[:5]:
    print(f"  {k}")

lock = r"D:\roms\library\roms\_importre_state\queue.lock"
if os.path.exists(lock):
    with open(lock, "r") as f:
        pid = f.read().strip()
    print(f"Lock file exists, PID: {pid}")
    # Verificar se o processo esta vivo
    try:
        os.kill(int(pid), 0)
        print(f"  Processo {pid} esta vivo")
    except:
        print(f"  Processo {pid} nao existe - lock stale")
        os.remove(lock)
        print("  Lock removido")
else:
    print("No lock file")
