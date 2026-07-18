import requests, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

session = requests.Session()
session.headers.update(HEADERS)

# Try the listing page
r = session.get('https://vimm.net/vault/?p=list&search=Backyard+Football', timeout=15)
print(f'Status: {r.status_code}, Length: {len(r.text)}')
# Save the full response for analysis
with open(r'F:\importre\_vimm_page.html', 'w', encoding='utf-8') as f:
    f.write(r.text)
print('Saved to _vimm_page.html')

# Also try the main vault page
r2 = session.get('https://vimm.net/vault/', timeout=15)
print(f'Vault main: {r2.status_code}, Length: {len(r2.text)}')

# Try direct game page with a known ID from cache
r3 = session.get('https://vimm.net/vault/5252', timeout=15)  # SLUS-01551 Easter Bunny
print(f'Vault/5252: {r3.status_code}, Length: {len(r3.text)}')
with open(r'F:\importre\_vimm_game.html', 'w', encoding='utf-8') as f:
    f.write(r3.text)

# Check for mediaId or download form
for label, text in [('list', r.text), ('game', r3.text)]:
    forms = re.findall(r'<form[^>]*>(.*?)</form>', text, re.S | re.I)
    print(f'\n{label}: {len(forms)} forms found')
    for i, form in enumerate(forms[:3]):
        action = re.search(r'action=["\']([^"\']*)["\']', form, re.I)
        method = re.search(r'method=["\']([^"\']*)["\']', form, re.I)
        inputs = re.findall(r'<input[^>]*>', form, re.I)
        print(f'  Form {i}: action={action.group(1) if action else "?"}, method={method.group(1) if method else "?"}')
        for inp in inputs[:5]:
            name = re.search(r'name=["\']([^"\']*)["\']', inp, re.I)
            value = re.search(r'value=["\']([^"\']*)["\']', inp, re.I)
            print(f'    input: name={name.group(1) if name else "?"}, value={value.group(1)[:30] if value else "?"}')
