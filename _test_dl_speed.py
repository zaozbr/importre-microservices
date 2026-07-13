"""Testa download direto (sem proxy) do archive.org"""
import requests, time

url = 'http://archive.org/download/hi-octane/Hi-Octane.iso'
try:
    t0 = time.time()
    r = requests.get(url, stream=True, timeout=(10, 30))
    print(f'Direto: Status={r.status_code} CL={r.headers.get("Content-Length","?")}')
    if r.status_code == 200:
        chunk = next(r.iter_content(8192))
        print(f'Primeiro chunk: {len(chunk)} bytes em {time.time()-t0:.1f}s')
except Exception as e:
    print(f'Direto falhou: {e}')

# Testar via Tor
proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
try:
    t0 = time.time()
    r = requests.get(url, stream=True, timeout=(30, 60), proxies=proxies)
    print(f'Tor: Status={r.status_code} CL={r.headers.get("Content-Length","?")}')
    if r.status_code == 200:
        # Baixar 1MB para medir velocidade
        total = 0
        t_start = time.time()
        for chunk in r.iter_content(8192):
            total += len(chunk)
            if total >= 1024*1024 or time.time() - t_start > 30:
                break
        elapsed = time.time() - t_start
        speed = total / elapsed if elapsed > 0 else 0
        print(f'Tor: {total} bytes em {elapsed:.1f}s = {speed/1024:.0f}KB/s')
except Exception as e:
    print(f'Tor falhou: {e}')
