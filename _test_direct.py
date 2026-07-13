import requests, time
t0 = time.time()
r = requests.get('http://archive.org/download/arcade_midnrun/midnrun.zip', timeout=15, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
print(f'Download direto: {r.status_code} em {time.time()-t0:.1f}s, size={r.headers.get("content-length","?")}')
r.close()
