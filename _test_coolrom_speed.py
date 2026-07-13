import requests
import time

url = "https://dl.coolrom.com/roms/psx/A%20Ressha%20de%20Ikou%204%20-%20Evolution%20%28Japan%29.7z/cTKy2dVL57yizvU2Qbh-bFVRbBIAjtCnKszay89Z1Vk/1783740320/"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

start = time.time()
r = requests.get(url, stream=True, timeout=30, headers=headers)
print(f"Status: {r.status_code}, headers: {r.headers.get('content-length')}")
downloaded = 0
last_report = start
for chunk in r.iter_content(chunk_size=1024*1024):
    if chunk:
        downloaded += len(chunk)
        now = time.time()
        if now - last_report > 3:
            speed = downloaded / (now - start) / 1024
            print(f"Downloaded {downloaded/1024/1024:.1f} MB, speed {speed:.1f} KB/s")
            last_report = now
        if downloaded > 20 * 1024 * 1024:  # testa 20MB
            break
end = time.time()
speed = downloaded / (end - start) / 1024
print(f"Final: {downloaded/1024/1024:.1f} MB em {end-start:.1f}s = {speed:.1f} KB/s")
