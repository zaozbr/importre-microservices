"""Diagnóstico completo: aria2c + importre + dashboard + dl_progress."""
import json, os, time, subprocess, sys

print("=" * 60)
print("DIAGNÓSTICO COMPLETO")
print("=" * 60)

# 1. aria2c
print("\n--- ARIA2C ---")
result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq aria2c.exe"], capture_output=True, text=True, timeout=5)
aria2c_running = "aria2c.exe" in result.stdout
print(f"Processo aria2c: {'RODANDO' if aria2c_running else 'MORTO'}")

# Tentar RPC
try:
    import urllib.request
    payload = json.dumps({"jsonrpc":"2.0","id":"diag","method":"aria2.getVersion","params":["token:psx_download_2026"]}).encode()
    req = urllib.request.Request("http://localhost:6801/jsonrpc", data=payload, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        print(f"RPC porta 6801: OK ({json.loads(r.read()).get('result',{}).get('version','?')})")
except Exception as e:
    print(f"RPC porta 6801: FALHOU ({e})")

# 2. Processos Python
print("\n--- PROCESSOS PYTHON ---")
result = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=5)
py_procs = [l for l in result.stdout.split("\n") if "python" in l.lower()]
print(f"Total processos python: {len(py_procs)}")
for p in py_procs:
    print(f"  {p.strip()}")

# 3. dl_progress.json
print("\n--- DL_PROGRESS.JSON ---")
p = r"D:\roms\library\roms\_importre_state\dl_progress.json"
if os.path.exists(p):
    age = int(time.time() - os.path.getmtime(p))
    size = os.path.getsize(p)
    print(f"Existe: sim | size={size} | age={age}s")
    try:
        d = json.load(open(p, "r", encoding="utf-8"))
        print(f"Itens: {len(d)}")
        for k, v in list(d.items())[:5]:
            if isinstance(v, dict):
                speed = v.get("speed", 0)
                downloaded = v.get("downloaded", 0)
                total = v.get("total", 0)
                print(f"  {k}: {downloaded}/{total} bytes speed={speed} status={v.get('status','?')}")
    except Exception as e:
        print(f"Erro ao ler: {e}")
else:
    print("Existe: NÃO")

# 4. Queue status
print("\n--- QUEUE ---")
q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
queue = q.get("queue", [])
ip = q.get("in_progress", {})
done = q.get("completed", {})
fail = q.get("failed", {})
if isinstance(done, dict):
    done_count = len(done)
elif isinstance(done, list):
    done_count = len(done)
else:
    done_count = 0
if isinstance(fail, dict):
    fail_count = len(fail)
elif isinstance(fail, list):
    fail_count = len(fail)
else:
    fail_count = 0
print(f"pending={len(queue)} ip={len(ip)} done={done_count} fail={fail_count}")

# Mostrar in_progress com fase
print("\nIn progress (primeiros 10):")
for k, v in list(ip.items())[:10]:
    if isinstance(v, dict):
        phase = v.get("_phase", "?")
        site = v.get("_current_site", "?")
        url = v.get("download_url", "SEM_URL")
        print(f"  {k}: phase={phase} site={site} url={url[:50] if url != 'SEM_URL' else 'SEM_URL'}")

# 5. Log recente
print("\n--- LOG RECENTE (últimas 10 linhas) ---")
try:
    lines = open(r"D:\roms\library\roms\_importre_state\importre.log", "r", encoding="utf-8", errors="replace").readlines()
    for l in lines[-10:]:
        print(f"  {l.rstrip()}")
except:
    print("  (sem log)")

# 6. Watchdog
print("\n--- WATCHDOG ---")
try:
    lines = open(r"D:\roms\library\roms\_importre_state\watchdog_autonomous.log", "r", encoding="utf-8", errors="replace").readlines()
    for l in lines[-5:]:
        print(f"  {l.rstrip()}")
except:
    print("  (sem log)")
