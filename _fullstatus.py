"""Verifica dashboard importre + aria2c + disco em uma vez."""
import urllib.request, json, os, time, sys

# 1. Dashboard importre
print("=== DASHBOARD IMPORTRE (porta 8765) ===")
try:
    r = urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=10)
    d = json.loads(r.read())
    q = d.get("queue", d.get("status", {}).get("queue", {}))
    if isinstance(q, dict):
        print(f"  pending: {len(q.get('queue', []))}")
        print(f"  completed: {len(q.get('completed', {}))}")
        print(f"  in_progress: {len(q.get('in_progress', {}))}")
        print(f"  failed: {len(q.get('failed', {}))}")
    status = d.get("status", {})
    print(f"  phase: {status.get('phase', '?')}")
    print(f"  workers: {status.get('workers', '?')}")
    # dl_progress
    dl = d.get("dl_progress", status.get("dl_progress", []))
    if isinstance(dl, list):
        print(f"  dl_progress: {len(dl)} items")
        for item in dl[:3]:
            if isinstance(item, dict):
                print(f"    {item.get('serial','?')}: {item.get('speed','?')} {item.get('status','?')}")
except Exception as e:
    print(f"  ERRO: {e}")

# 2. Aria2c RPC
print("\n=== ARIA2C RPC (porta 6801) ===")
try:
    req = urllib.request.Request(
        "http://127.0.0.1:6801/jsonrpc",
        data=json.dumps({"jsonrpc": "2.0", "id": "1", "method": "aria2.getGlobalStat", "params": ["psx_download_2026"]}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
        result = data.get("result", {})
        speed = int(result.get("downloadSpeed", 0))
        print(f"  speed: {speed/1024/1024:.2f}MB/s ({speed/1024:.0f}KB/s)")
        print(f"  active: {result.get('numActive')}")
        print(f"  waiting: {result.get('numWaiting')}")
        print(f"  stopped: {result.get('numStopped')}")
except Exception as e:
    print(f"  ERRO: {e}")

# 3. Disco
print("\n=== DISCO ===")
d = r"D:\roms\library\roms\_importre_state\downloads"
files = os.listdir(d)
total = sum(os.path.getsize(os.path.join(d, f)) for f in files if os.path.isfile(os.path.join(d, f)))
aria2 = [f for f in files if f.endswith(".aria2")]
print(f"  Arquivos: {len(files)} ({len(aria2)} em download)")
print(f"  Tamanho: {total/1024**3:.2f}GB")

# 4. Queue.json
print("\n=== QUEUE.JSON ===")
q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
print(f"  pending: {len(q.get('queue', []))}")
print(f"  completed: {len(q.get('completed', {}))}")
print(f"  in_progress: {len(q.get('in_progress', {}))}")
print(f"  failed: {len(q.get('failed', {}))}")

# 5. Processos
print("\n=== PROCESSOS ===")
import subprocess
r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq aria2c.exe"], capture_output=True, text=True)
aria2_count = r.stdout.count("aria2c.exe")
print(f"  aria2c: {aria2_count} instâncias")
r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq pythonw.exe"], capture_output=True, text=True)
print(f"  pythonw: {r.stdout.count('pythonw.exe')} instâncias")
r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe"], capture_output=True, text=True)
print(f"  python: {r.stdout.count('python.exe')} instâncias")
