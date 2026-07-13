import requests, re
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Testar retroiso para um item JP
serial = 'SLPM-86975'
name = 'Simple 1500 Series Vol.91 - The Gambler'

url = f"https://www.retroiso.com/search?q={name.replace(' ', '+')}"
print(f"Search: {url}")
r = requests.get(url, timeout=15, headers=headers)
print(f"Status: {r.status_code}, len: {len(r.text)}")

soup = BeautifulSoup(r.text, 'lxml')
for a in soup.find_all('a', href=True):
    text = a.get_text(strip=True).lower()
    if 'gambler' in text or '1500' in text:
        print(f"Link: {a['href']} text: {a.get_text(strip=True)[:80]}")
