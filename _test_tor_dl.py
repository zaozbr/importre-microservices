import requests
proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
try:
    r = requests.get('http://archive.org/download/hi-octane/Hi-Octane.iso', proxies=proxies, stream=True, timeout=30)
    print(f'Status: {r.status_code}')
    cl = r.headers.get('Content-Length', 'unknown')
    print(f'Content-Length: {cl}')
    chunk = next(r.iter_content(1024))
    print(f'Primeiro chunk: {len(chunk)} bytes')
except Exception as e:
    print(f'Erro: {e}')
