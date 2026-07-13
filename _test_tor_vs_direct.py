"""Compara velocidade: download direto vs Tor para archive.org.
Testa se Tor ajuda a contornar o limite de 0.2MB/s por IP do archive.org.
"""
import time
import requests
import os

# URL de arquivo pequeno no archive.org para teste
TEST_URL = "http://archive.org/download/psx-ntscj-chd-zstd/ntscj/Lethal%20Enforcers%20Deluxe%20Pack%20%28Japan%29.chd"
# Usar range para baixar só 5MB
HEADERS = {"Range": "bytes=0-5242880", "User-Agent": "Mozilla/5.0"}

def test_direct():
    """Download direto (sem proxy)."""
    print("--- Download DIRETO (5MB) ---")
    try:
        t0 = time.time()
        resp = requests.get(TEST_URL, headers=HEADERS, stream=True, timeout=30)
        resp.raise_for_status()
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=256*1024):
            downloaded += len(chunk)
        elapsed = time.time() - t0
        speed = downloaded / elapsed
        print(f"  Baixado: {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s")
        return speed
    except Exception as e:
        print(f"  ERRO: {e}")
        return 0

def test_tor():
    """Download via Tor (SOCKS5 porta 9050)."""
    print("\n--- Download via TOR (5MB) ---")
    proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}
    try:
        t0 = time.time()
        resp = requests.get(TEST_URL, headers=HEADERS, stream=True, timeout=60, proxies=proxies)
        resp.raise_for_status()
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=256*1024):
            downloaded += len(chunk)
        elapsed = time.time() - t0
        speed = downloaded / elapsed
        print(f"  Baixado: {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s")
        return speed
    except Exception as e:
        print(f"  ERRO: {e}")
        return 0

def test_tor_new_identity():
    """Download via Tor com novo circuito (stream isolation por request)."""
    print("\n--- Download via TOR + Stream Isolation (5MB) ---")
    # Usar socks5h para DNS via Tor (cada conexão pode usar circuito diferente)
    proxies = {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}
    try:
        t0 = time.time()
        resp = requests.get(TEST_URL, headers=HEADERS, stream=True, timeout=60, proxies=proxies)
        resp.raise_for_status()
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=256*1024):
            downloaded += len(chunk)
        elapsed = time.time() - t0
        speed = downloaded / elapsed
        print(f"  Baixado: {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s")
        return speed
    except Exception as e:
        print(f"  ERRO: {e}")
        return 0

if __name__ == "__main__":
    print("=" * 60)
    print("COMPARAÇÃO: Direto vs Tor vs Tor+StreamIsolation")
    print("=" * 60)
    
    # Verificar se requests suporta SOCKS5
    try:
        import socks  # PySocks
        print("PySocks: instalado")
    except ImportError:
        print("PySocks: NÃO instalado — instalar com: pip install pysocks")
        print("Testando apenas direto...")
        test_direct()
        exit()
    
    speed_direct = test_direct()
    speed_tor = test_tor()
    speed_tor_iso = test_tor_new_identity()
    
    print("\n" + "=" * 60)
    print("RESULTADO:")
    print(f"  Direto:           {speed_direct/1024/1024:.2f}MB/s")
    print(f"  Tor:              {speed_tor/1024/1024:.2f}MB/s")
    print(f"  Tor+StreamIso:    {speed_tor_iso/1024/1024:.2f}MB/s")
    
    if speed_tor > speed_direct * 1.5:
        print("\n  >> Tor é SIGNIFICATIVAMENTE mais rápido — vale a pena!")
    elif speed_tor > speed_direct:
        print("\n  >> Tor é marginalmente mais rápido — talvez não valha a pena")
    else:
        print("\n  >> Tor é MAIS LENTO que direto — não vale a pena para downloads")
    
    # Verificar IP de saída do Tor
    try:
        proxies = {"http": "socks5h://127.0.0.1:9050"}
        resp = requests.get("http://httpbin.org/ip", timeout=30, proxies=proxies)
        print(f"\n  IP de saída do Tor: {resp.json()}")
    except:
        pass
