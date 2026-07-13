"""Testa cookies do archive.org para acessar coleções restritas."""
import requests, urllib3
from urllib.parse import quote

urllib3.disable_warnings()

COOKIES = {
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
}

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
s.cookies.update(COOKIES)

# Testar download de coleção restrita (Redump.orgSonyPlayStation-PAL-R)
url = 'http://archive.org/download/Redump.orgSonyPlayStation-PAL-R/Rapid%20Reload%20%28Europe%29.zip'
print(f'Testando: {url[:80]}...')

# 1. HEAD request
r = s.head(url, timeout=15, allow_redirects=True)
print(f'HEAD Status: {r.status_code}')
print(f'Content-Length: {r.headers.get("content-length", "N/A")}')
print(f'Accept-Ranges: {r.headers.get("accept-ranges", "N/A")}')

# 2. GET com Range
r2 = s.get(url, timeout=15, stream=True, headers={'Range': 'bytes=0-1023'})
print(f'\nGET Range Status: {r2.status_code}')
print(f'Content-Range: {r2.headers.get("content-range", "N/A")}')
print(f'Content-Length: {r2.headers.get("content-length", "N/A")}')

if r2.status_code in (200, 206):
    data = r2.content
    print(f'\nSUCESSO! Baixou {len(data)} bytes')
    print(f'Primeiros bytes: {data[:20]}')
r2.close()

# Testar psx-roms-archive tambem
print(f'\n--- Testando psx-roms-archive ---')
url2 = 'http://archive.org/download/psx-roms-archive/buster-bros.-collection-u-slus-00208-.7z'
r3 = s.get(url2, timeout=15, stream=True, headers={'Range': 'bytes=0-1023'})
print(f'GET Range Status: {r3.status_code}')
print(f'Content-Range: {r3.headers.get("content-range", "N/A")}')
r3.close()
