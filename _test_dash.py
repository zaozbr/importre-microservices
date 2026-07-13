"""Testa latencia do servidor."""
import urllib.request, json, time

# Testar endpoint fast
t0 = time.time()
r = urllib.request.urlopen("http://127.0.0.1:8765/api/status/fast", timeout=5)
data = json.loads(r.read())
lat = (time.time() - t0) * 1000
s = data["status"]
print(f"=== /api/status/fast ===")
print(f"Latencia: {lat:.0f}ms")
print(f"Pending: {s['pending']}, InProgress: {s['in_progress']}, Completed: {s['completed']}, Failed: {s['failed']}")
print(f"Downloading: {s['downloading']}, Searching: {s['searching']}, Starting: {s['starting']}")
print(f"DL progress items: {len(s.get('dl_progress', {}))}")
print(f"In progress items: {len(s.get('in_progress_items', {}))}")

# Testar endpoint full
t0 = time.time()
r = urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=5)
data = json.loads(r.read())
lat = (time.time() - t0) * 1000
print(f"\n=== /api/status (full) ===")
print(f"Latencia: {lat:.0f}ms")
print(f"Sites: {len(data.get('sites', {}))}")
print(f"Cover count: {data.get('cover_count', 0)}")
print(f"Process state: {data.get('process_state', '?')}")

# Testar 5 requisicoes rapidas
print(f"\n=== Stress test (5x fast) ===")
for i in range(5):
    t0 = time.time()
    r = urllib.request.urlopen("http://127.0.0.1:8765/api/status/fast", timeout=5)
    r.read()
    print(f"  Req {i+1}: {(time.time()-t0)*1000:.0f}ms")
