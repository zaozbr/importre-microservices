"""Testa archive.org com cookies via requests — verifica se auth funciona."""
import requests, time

COOKIES = {
    "logged-in-sig": "1815424048%201783888048%20NdcQZOzCA4CB%2BcoaGKXMv8yc%2FQ0uKS0DS7NHsVPyFUzCWjdaAjvSnGTdPdq6DwibaBL1t1%2BX001Lp626v%2BnwpQd6OcSm3ooULfGMPlxfQwIWKJWo9cV906yT6IRVmZOrso8y0nUYy%2BiuoC6xLYaXww3uiRYjdElmQJYDarrLK3PEx88JZfG4NXZTXRKvFD74XXWVsftXlRoU6fyfRkPmcExzl9HK1%2FloDawy1Nydw2ChC3v9HMqejk0iqMc0k21ZK0HJs9ofXsmjMnacziSSD1ZgxOKp8uO5AQKtZxlKEplK27uEvzq5PoUsJv7Kfsh7gZp1cilR2sW3c03iP8roGw%3D%3D",
    "logged-in-user": "zaozao2%40gmail.com",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Testar 5 URLs diferentes
urls = [
    ("psx-ntscj-chd-zstd", "https://archive.org/download/psx-ntscj-chd-zstd/ntscj/Nice%20Price%20Series%20Vol.%2003%20-%20Hanafuda%20%26%20Card%20Game%20%28Japan%29.chd"),
    ("psx-pal-chd-zstd", "https://archive.org/download/psx-pal-chd-zstd/pal/All%20Star%20Boxing%20%28Europe%29.chd"),
    ("Redump", "https://archive.org/download/Redump_PSX_2021_06_04_A_C/A%20IV%20Evolution%20%28Japan%29.zip"),
    ("CuratedPSX", "https://archive.org/download/CuratedPSXRedumpCHDs/Simple%201500%20Series%20Vol.%2011%20-%20The%20Pinball%20-%203D%20%28Japan%29.chd"),
    ("psx-chd-roms-s", "https://archive.org/download/psx-chd-roms-s/Soumatou%20%28Japan%29%20%28Demo%29.chd"),
]

for name, url in urls:
    # Sem cookies
    try:
        r = requests.head(url, timeout=15, headers=HEADERS, allow_redirects=True)
        status_no = r.status_code
        size_no = r.headers.get("Content-Length", "?")
    except Exception as e:
        status_no = f"ERR:{str(e)[:40]}"
        size_no = "?"
    
    # Com cookies
    try:
        r = requests.head(url, timeout=15, headers=HEADERS, cookies=COOKIES, allow_redirects=True)
        status_auth = r.status_code
        size_auth = r.headers.get("Content-Length", "?")
        final_url = r.url[:80]
    except Exception as e:
        status_auth = f"ERR:{str(e)[:40]}"
        size_auth = "?"
        final_url = "?"
    
    print(f"{name}:")
    print(f"  sem auth: {status_no} size={size_no}")
    print(f"  com auth: {status_auth} size={size_auth} host={final_url}")
    print()

# Testar velocidade (5MB) com cookies
print("=== TESTE VELOCIDADE (5MB) ===")
for name, url in urls[:3]:
    try:
        t0 = time.time()
        r = requests.get(url, headers={**HEADERS, "Range": "bytes=0-5242880"},
                        cookies=COOKIES, stream=True, timeout=30, allow_redirects=True)
        r.raise_for_status()
        downloaded = 0
        for chunk in r.iter_content(chunk_size=256*1024):
            downloaded += len(chunk)
        elapsed = time.time() - t0
        speed = downloaded / elapsed if elapsed > 0 else 0
        host = r.url.split("/")[2] if "://" in r.url else "?"
        print(f"  {name}: {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s (host={host})")
    except Exception as e:
        print(f"  {name}: ERRO — {str(e)[:100]}")
