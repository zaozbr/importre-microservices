import requests, time
t0 = time.time()
try:
    r = requests.get("https://archive.org/metadata/psx-ntscj-chd-zstd", timeout=8)
    print(f"status={r.status_code} time={time.time()-t0:.1f}s")
except Exception as e:
    print(f"ERRO: {e} time={time.time()-t0:.1f}s")
