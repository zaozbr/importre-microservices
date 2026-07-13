import requests
import time

url = "https://dl.coolrom.com/roms/psx/Simple%201500%20Series%20Vol.91%20-%20The%20Gambler%20-%20Honoo%20no%20Tobaku%20Densetsu%20%28Japan%29.7z/"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

try:
    r = requests.get(url, stream=True, timeout=15, headers=headers)
    print(f"Status: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    print(f"URL final: {r.url}")
    print(f"Texto: {r.text[:200]}")
    if r.status_code == 200:
        downloaded = 0
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk:
                downloaded += len(chunk)
                if downloaded > 5 * 1024 * 1024:
                    break
        print(f"Downloaded {downloaded/1024/1024:.1f} MB")
except Exception as e:
    print(f"Erro: {e}")
