import requests

# Test downloading CHD from psxgames collection using archive.org/download/ (no server prefix)
test_items = [
    ('psx_vigil8a', 'playstationdisc.chd'),
    ('psx_vigil8', 'playstationdisc.chd'),
    ('psx_wpoutxlp', 'playstationdisc.chd'),
    ('psx_rpgmaker', 'playstationdisc.chd'),
]

for identifier, filename in test_items:
    url = f'https://archive.org/download/{identifier}/{filename}'
    try:
        r = requests.head(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True)
        size = r.headers.get('content-length', '?')
        print(f'{r.status_code} | {identifier}/{filename} | size={size}')
    except Exception as e:
        print(f'ERR | {identifier} | {e}')
