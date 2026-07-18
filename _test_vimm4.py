import requests, re, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

session = requests.Session()
session.headers.update(HEADERS)

# Test with correct parameter 'q' instead of 'search'
r = session.get('https://vimm.net/vault/?p=list&q=Backyard+Football', timeout=30)
print(f'Search q=Backyard+Football: {r.status_code}, Length: {len(r.text)}')

# Save for analysis
with open(r'F:\importre\_vimm_search.html', 'w', encoding='utf-8') as f:
    f.write(r.text)

# Find vault links
from bs4 import BeautifulSoup
soup = BeautifulSoup(r.text, 'html.parser')
for a in soup.find_all('a', href=True):
    href = a['href']
    text = a.get_text(strip=True)
    if '/vault/' in href and href != '/vault' and not href.startswith('/vault/PS') and text:
        print(f'  {href} -> {text[:80]}')

time.sleep(3)

# Try a direct game page
r2 = session.get('https://vimm.net/vault/5252', timeout=30)
print(f'\nVault/5252: {r2.status_code}, Length: {len(r2.text)}')
if r2.status_code == 200:
    with open(r'F:\importre\_vimm_game.html', 'w', encoding='utf-8') as f:
        f.write(r2.text)
    # Find download form
    forms = re.findall(r'<form[^>]*>(.*?)</form>', r2.text, re.S | re.I)
    print(f'Forms: {len(forms)}')
    for i, form in enumerate(forms[:5]):
        action = re.search(r'action=["\']([^"\']*)["\']', form, re.I)
        method = re.search(r'method=["\']([^"\']*)["\']', form, re.I)
        inputs = re.findall(r'<input[^>]*>', form, re.I)
        print(f'  Form {i}: action={action.group(1) if action else "?"}, method={method.group(1) if method else "?"}')
        for inp in inputs[:5]:
            name = re.search(r'name=["\']([^"\']*)["\']', inp, re.I)
            value = re.search(r'value=["\']([^"\']*)["\']', inp, re.I)
            print(f'    input: name={name.group(1) if name else "?"}, value={value.group(1)[:30] if value else "?"}')
