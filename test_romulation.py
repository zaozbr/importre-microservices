import requests, re
from bs4 import BeautifulSoup

url='https://www.romulation.org/roms/newdownload/guest/9646/eyJpdiI6ImV5RVpjRlIwSTRUNG10RWc5Wk0vNnc9PSIsInZhbHVlIjoiVVRia0xhV0JjNGEvU2dhSVkzMXZETXVxdHJUekc3QXlPVG9wSThpWmdzTT0iLCJtYWMiOiIzMjE5OWY2YzFiMDFmMWMzYzM2NDIwYWM3MzRmZDU1ZGE4NTEyNmIzYjUzN2QxNTg5ZDkxNmQ4MTE4ZGY3M2NiIiwidGFnIjoiIn0='
r=requests.get(url, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36','Referer':'https://www.romulation.org/rom/PSX/Vigilante-8'}, timeout=30)
print('status',r.status_code)
print('final url',r.url[:150])
links=re.findall(r'https://pluto\.romulation\.net/files/guest/[^\s"<>]+', r.text)
print('pluto links:', links[:3])
if not links:
    soup=BeautifulSoup(r.text,'html.parser')
    for a in soup.find_all('a', href=True):
        if 'pluto' in a['href'] or 'download' in a['href'].lower():
            print('A LINK:', a['href'][:150])
    for meta in soup.find_all('meta'):
        if 'refresh' in str(meta).lower():
            print('META:', str(meta)[:200])
    print('text sample:', r.text[:800])
