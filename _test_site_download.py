import requests, re
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
serial = 'SLUS-00426'
name = 'MDK'

# Testar consoleroms
print("=== consoleroms ===")
url = f"https://www.consoleroms.com/roms/psx?q={name.replace(' ', '+')}"
r = requests.get(url, timeout=10, headers=headers)
soup = BeautifulSoup(r.text, 'lxml')
for a in soup.find_all('a', href=True):
    if serial.lower() in a.get_text(strip=True).lower() or 'download' in a.get_text(strip=True).lower():
        print(f"Link: {a['href']} text: {a.get_text(strip=True)[:60]}")

# Testar romulation
print("\n=== romulation ===")
url = f"https://www.romulation.org/roms/PSX?q={name.replace(' ', '+')}"
r = requests.get(url, timeout=10, headers=headers)
soup = BeautifulSoup(r.text, 'lxml')
for a in soup.find_all('a', href=True):
    text = a.get_text(strip=True).lower()
    if serial.lower() in text or 'download' in text or 'rom' in text:
        print(f"Link: {a['href']} text: {a.get_text(strip=True)[:60]}")

# Testar blueroms
print("\n=== blueroms ===")
url = f"https://www.blueroms.ws/ps1?search={name.replace(' ', '+')}"
r = requests.get(url, timeout=10, headers=headers)
soup = BeautifulSoup(r.text, 'lxml')
for a in soup.find_all('a', href=True):
    text = a.get_text(strip=True).lower()
    if serial.lower() in text or 'download' in text:
        print(f"Link: {a['href']} text: {a.get_text(strip=True)[:60]}")
