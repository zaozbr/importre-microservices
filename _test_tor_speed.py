"""Testa velocidade real: download via Tor proxy vs direto para archive.org.
Baixa 5MB de um arquivo real do archive.org.
"""
import time
import requests

# URL real que está no índice
URL = "http://archive.org/download/psx-ntscj-chd-zstd/ntscj/Lethal%20Enforcers%20Deluxe%20Pack%20%28Japan%29.chd"
HEADERS = {"Range": "bytes=0-5242880", "User-Agent": "Mozilla/5.0"}  # 5MB

def test_direct():
    print("--- DIRETO (5MB) ---")
    try:
        t0 = time.time()
        resp = requests.get(URL, headers=HEADERS, stream=True, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=256*1024):
            downloaded += len(chunk)
        elapsed = time.time() - t0
        speed = downloaded / elapsed if elapsed > 0 else 0
        print(f"  {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s")
        return speed
    except Exception as e:
        print(f"  ERRO: {e}")
        return 0

def test_tor():
    print("\n--- VIA TOR PROXY (5MB) ---")
    proxies = {"http": "http://127.0.0.1:8118", "https": "http://127.0.0.1:8118"}
    try:
        t0 = time.time()
        resp = requests.get(URL, headers=HEADERS, stream=True, timeout=60, proxies=proxies, allow_redirects=True)
        resp.raise_for_status()
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=256*1024):
            downloaded += len(chunk)
        elapsed = time.time() - t0
        speed = downloaded / elapsed if elapsed > 0 else 0
        print(f"  {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s")
        return speed
    except Exception as e:
        print(f"  ERRO: {e}")
        return 0

def test_tor_socks():
    print("\n--- VIA TOR SOCKS5 direto (5MB) ---")
    proxies = {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}
    try:
        t0 = time.time()
        resp = requests.get(URL, headers=HEADERS, stream=True, timeout=60, proxies=proxies, allow_redirects=True)
        resp.raise_for_status()
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=256*1024):
            downloaded += len(chunk)
        elapsed = time.time() - t0
        speed = downloaded / elapsed if elapsed > 0 else 0
        print(f"  {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s")
        return speed
    except Exception as e:
        print(f"  ERRO: {e}")
        return 0

if __name__ == "__main__":
    print("=" * 60)
    print("TESTE DE VELOCIDADE: Direto vs Tor Proxy vs Tor SOCKS5")
    print("=" * 60)
    
    s1 = test_direct()
    s2 = test_tor()
    s3 = test_tor_socks()
    
    print("\n" + "=" * 60)
    print(f"Direto:        {s1/1024/1024:.2f}MB/s")
    print(f"Tor Proxy:     {s2/1024/1024:.2f}MB/s")
    print(f"Tor SOCKS5:    {s3/1024/1024:.2f}MB/s")
    
    # Verificar IP de saída
    try:
        proxies = {"http": "http://127.0.0.1:8118"}
        resp = requests.get("http://httpbin.org/ip", timeout=30, proxies=proxies)
        print(f"\nIP saída Tor Proxy: {resp.json()}")
    except:
        pass
    try:
        resp = requests.get("http://httpbin.org/ip", timeout=15)
        print(f"IP saída Direto: {resp.json()}")
    except:
        pass
