import requests, time
# Testar HTTP (nao HTTPS)
t0 = time.time()
try:
    r = requests.get("http://archive.org/metadata/psx-ntscj-chd-zstd", timeout=10, allow_redirects=False)
    print(f"HTTP status={r.status_code} time={time.time()-t0:.1f}s headers={dict(r.headers)}")
except Exception as e:
    print(f"HTTP ERRO: {e} time={time.time()-t0:.1f}s")

# Testar HTTPS com session
t0 = time.time()
try:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    r = s.get("https://archive.org/metadata/psx-ntscj-chd-zstd", timeout=10)
    print(f"HTTPS status={r.status_code} time={time.time()-t0:.1f}s")
except Exception as e:
    print(f"HTTPS ERRO: {e} time={time.time()-t0:.1f}s")
