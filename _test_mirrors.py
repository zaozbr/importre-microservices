"""Testa mirrors do archive.org para download mais rápido."""
import requests, time

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

# URL original
url = 'http://archive.org/download/jetracer-eu/Jetracer%20%28EU%29.zip'

# Primeiro fazer redirect para descobrir o mirror
print("Testando redirect...")
r = s.get(url, timeout=10, stream=True, allow_redirects=False)
print(f"Status: {r.status_code}")
print(f"Location: {r.headers.get('Location', 'N/A')}")

if r.status_code in (301, 302, 303, 307, 308):
    mirror_url = r.headers.get('Location', '')
    print(f"\nMirror URL: {mirror_url}")

    # Testar velocidade do mirror
    print("Baixando 5MB do mirror...")
    t0 = time.time()
    r2 = s.get(mirror_url, timeout=10, stream=True)
    dl = 0
    for chunk in r2.iter_content(chunk_size=2 * 1024 * 1024):
        if chunk:
            dl += len(chunk)
            if dl >= 5 * 1024 * 1024:
                break
    elapsed = time.time() - t0
    speed = dl / elapsed
    print(f"  {dl/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024:.0f}KB/s")
    r2.close()

# Também testar URL original
print("\nTestando URL original...")
t0 = time.time()
r3 = s.get(url, timeout=10, stream=True)
dl = 0
for chunk in r3.iter_content(chunk_size=2 * 1024 * 1024):
    if chunk:
        dl += len(chunk)
        if dl >= 5 * 1024 * 1024:
            break
elapsed = time.time() - t0
speed = dl / elapsed
print(f"  {dl/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024:.0f}KB/s")
r3.close()
