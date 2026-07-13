import requests, urllib3
urllib3.disable_warnings()
s = requests.Session()
s.proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
s.headers.update({'User-Agent': 'Mozilla/5.0'})

# Testar GET com Range em colecao restrita
url = 'http://archive.org/download/Redump.orgSonyPlayStation-PAL-R/Rapid%20Reload%20%28Europe%29.zip'
r = s.get(url, timeout=(15, 30), stream=True, headers={'Range': 'bytes=0-0'})
print(f'Status: {r.status_code}')
cr = r.headers.get('content-range', 'N/A')
cl = r.headers.get('content-length', 'N/A')
ar = r.headers.get('accept-ranges', 'N/A')
print(f'Content-Range: {cr}')
print(f'Content-Length: {cl}')
print(f'Accept-Ranges: {ar}')
r.close()
