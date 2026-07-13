"""Testa archive_request do importre.py com proxy Tor."""
import sys, time
sys.path.insert(0, r'D:\roms\library\roms\psx')
os_chdir = r'D:\roms\library\roms\psx'
import os
os.chdir(os_chdir)

# Importar archive_request do importre
from importre import archive_request

print("=== TESTE archive_request com proxy Tor ===\n")

# Teste 1: search
t0 = time.time()
try:
    r = archive_request("get", "https://archive.org/advancedsearch.php?q=%22SLPM-87140%22&fl[]=identifier&fl[]=title&rows=5&output=json",
                        timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    print(f"Search: {r.status_code} em {time.time()-t0:.1f}s")
    if r.status_code == 200:
        docs = r.json().get("response", {}).get("docs", [])
        for d in docs:
            print(f"  {d.get('identifier','')}: {d.get('title','')[:80]}")
except Exception as e:
    print(f"ERRO: {e}")

# Teste 2: metadata
print("\n--- Metadata ---")
t0 = time.time()
try:
    r = archive_request("get", "https://archive.org/metadata/psx_ss099knd", timeout=30)
    print(f"Metadata: {r.status_code} em {time.time()-t0:.1f}s")
    if r.status_code == 200:
        data = r.json()
        files = data.get("files", [])
        rom_files = [f for f in files if f.get("name", "").endswith((".7z", ".zip", ".iso", ".bin", ".chd"))]
        print(f"  {len(rom_files)} arquivos de ROM:")
        for f in rom_files[:5]:
            print(f"    {f.get('name','')} ({f.get('size','?')} bytes)")
except Exception as e:
    print(f"ERRO: {e}")

# Teste 3: download (HEAD apenas)
print("\n--- Download HEAD ---")
t0 = time.time()
try:
    r = archive_request("get", "https://archive.org/download/psx_ss099knd/Simple%201500%20Series%20Vol.99%20-%20The%20Kendo%20-%20Ken%20no%20Hanamichi%20(Jpn).7z",
                        stream=True, timeout=(10, 30), headers={"User-Agent": "Mozilla/5.0"})
    print(f"Download: {r.status_code} em {time.time()-t0:.1f}s")
    print(f"  Content-Length: {r.headers.get('Content-Length', '?')}")
    r.close()
except Exception as e:
    print(f"ERRO: {e}")
