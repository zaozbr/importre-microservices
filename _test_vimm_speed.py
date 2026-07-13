import requests
import time

# Testar um download do vimm
url = "https://archival.cat/PS1/5262.7z"
headers = {'User-Agent': 'Mozilla/5.0'}
start = time.time()
try:
    r = requests.get(url, stream=True, timeout=(10, 30), headers=headers)
    print(f"Status: {r.status_code}, headers: {r.headers.get('content-length')}")
    downloaded = 0
    for chunk in r.iter_content(chunk_size=1024*1024):
        if chunk:
            downloaded += len(chunk)
            if downloaded > 5 * 1024 * 1024:
                break
    end = time.time()
    speed = downloaded / (end - start) / 1024
    print(f"Downloaded {downloaded/1024/1024:.1f} MB in {end-start:.1f}s = {speed:.1f} KB/s")
except Exception as e:
    print(f"Erro: {e}")
