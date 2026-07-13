"""Testa archive.org e coolrom diretamente para ver se estao respondendo."""
import requests, time, json, os

# Carregar cookies do archive.org
cookies_path = r"D:\roms\library\roms\_importre_state\archive_session.json"
cookies = {}
if os.path.exists(cookies_path):
    with open(cookies_path) as f:
        data = json.load(f)
        cookies = {c["name"]: c["value"] for c in data.get("cookies", [])}
    print(f"Cookies carregados: {len(cookies)} chaves")

# Test 1: archive.org metadata
print("\n=== archive.org metadata ===")
t0 = time.time()
try:
    r = requests.get("https://archive.org/metadata/psx-ntscj-chd-zstd", 
                     cookies=cookies, timeout=15)
    print(f"  status={r.status_code} time={time.time()-t0:.1f}s")
    if r.status_code == 200:
        d = r.json()
        files = d.get("files", [])
        print(f"  files: {len(files)}")
except Exception as e:
    print(f"  ERRO: {e}")

# Test 2: archive.org download (HEAD)
print("\n=== archive.org download HEAD ===")
t0 = time.time()
try:
    r = requests.head("https://archive.org/download/psx-ntscj-chd-zstd/ntscj/Nice%20Price%20Series%20Vol.%2003%20-%20Hanafuda%20%26%20Card%20Game%20%28Japan%29.chd",
                      cookies=cookies, timeout=15, allow_redirects=True)
    print(f"  status={r.status_code} time={time.time()-t0:.1f}s size={r.headers.get('Content-Length','?')}")
except Exception as e:
    print(f"  ERRO: {e}")

# Test 3: archive.org download (5MB range)
print("\n=== archive.org download 5MB ===")
t0 = time.time()
try:
    r = requests.get("https://archive.org/download/psx-ntscj-chd-zstd/ntscj/Nice%20Price%20Series%20Vol.%2003%20-%20Hanafuda%20%26%20Card%20Game%20%28Japan%29.chd",
                     cookies=cookies, timeout=30, stream=True,
                     headers={"Range": "bytes=0-5242880"}, allow_redirects=True)
    r.raise_for_status()
    downloaded = 0
    for chunk in r.iter_content(chunk_size=256*1024):
        downloaded += len(chunk)
    elapsed = time.time() - t0
    speed = downloaded / elapsed if elapsed > 0 else 0
    print(f"  {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s")
except Exception as e:
    print(f"  ERRO: {e}")

# Test 4: coolrom (URL antiga - provavelmente expirada)
print("\n=== coolrom URL antiga ===")
t0 = time.time()
try:
    r = requests.head("https://dl.coolrom.com/roms/psx/Vib-Ribbon%20%28Japan%29.7z/_p2aPY5ua2hTaN_f_GqZHR39HBPbRthvlzqKGOFWg6o/1783895423/",
                      timeout=15, allow_redirects=True)
    print(f"  status={r.status_code} time={time.time()-t0:.1f}s")
except Exception as e:
    print(f"  ERRO: {e}")

# Test 5: coolrom página de detalhe (para gerar URL fresca)
print("\n=== coolrom pagina de detalhe ===")
t0 = time.time()
try:
    r = requests.get("https://coolrom.com/roms/psx/vib-ribbon-japan/1783895423",
                     timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    print(f"  status={r.status_code} time={time.time()-t0:.1f}s size={len(r.text)} chars")
    if r.status_code == 200 and "dl.coolrom.com" in r.text:
        import re
        m = re.search(r'(https://dl\.coolrom\.com/roms/[^"\'<]+)', r.text)
        if m:
            print(f"  URL fresca: {m.group(1)}")
except Exception as e:
    print(f"  ERRO: {e}")
