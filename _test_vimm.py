import requests, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

session = requests.Session()
session.headers.update(HEADERS)

# Test 1: Search for a game on Vimm
search_term = "Backyard Football"
url = f'https://vimm.net/vault/?p=listing&search={requests.utils.quote(search_term)}'
print(f'Searching: {url}')
r = session.get(url, timeout=30)
print(f'Status: {r.status_code}, Length: {len(r.text)}')

# Find game links
links = re.findall(r'/vault/(\d+)', r.text)
print(f'Found vault IDs: {links[:10]}')

# Also look for the game title near the link
from bs4 import BeautifulSoup
soup = BeautifulSoup(r.text, 'html.parser')
for a in soup.find_all('a', href=True):
    if '/vault/' in a['href'] and a.get_text(strip=True):
        print(f'  Link: {a["href"]} -> {a.get_text(strip=True)[:60]}')
