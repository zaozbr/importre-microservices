"""Testa conectividade com archive.org."""
import requests, time

# Testar metadata API
t0 = time.time()
try:
    r = requests.get("https://archive.org/metadata/psx_bublbobl", timeout=10)
    print(f"Metadata API: {r.status_code} em {(time.time()-t0)*1000:.0f}ms")
except Exception as e:
    print(f"Metadata API: FALHOU em {(time.time()-t0)*1000:.0f}ms - {str(e)[:100]}")

# Testar download HTTPS
t0 = time.time()
try:
    r = requests.get("https://archive.org/download/psx_bublbobl/playstationdisc.chd", stream=True, timeout=(10, 5), headers={"User-Agent": "Mozilla/5.0"})
    cl = r.headers.get("content-length", "?")
    print(f"Download HTTPS: {r.status_code} em {(time.time()-t0)*1000:.0f}ms, size={cl}")
    r.close()
except Exception as e:
    print(f"Download HTTPS: FALHOU em {(time.time()-t0)*1000:.0f}ms - {str(e)[:100]}")

# Testar download HTTP
t0 = time.time()
try:
    r = requests.get("http://archive.org/download/psx_bublbobl/playstationdisc.chd", stream=True, timeout=(10, 5), headers={"User-Agent": "Mozilla/5.0"})
    print(f"Download HTTP: {r.status_code} em {(time.time()-t0)*1000:.0f}ms")
    r.close()
except Exception as e:
    print(f"Download HTTP: FALHOU em {(time.time()-t0)*1000:.0f}ms - {str(e)[:100]}")

# Testar coolrom
t0 = time.time()
try:
    r = requests.get("https://dl.coolrom.com/roms/psx/", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    print(f"CoolROM: {r.status_code} em {(time.time()-t0)*1000:.0f}ms")
except Exception as e:
    print(f"CoolROM: FALHOU em {(time.time()-t0)*1000:.0f}ms - {str(e)[:100]}")
