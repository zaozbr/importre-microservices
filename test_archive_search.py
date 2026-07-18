import requests, json
from urllib.parse import quote

# Test different search approaches for SLUS-00510
serial = 'SLUS-00510'

# Test 1: quoted serial
query1 = f'"{serial}"'
url1 = f'https://archive.org/advancedsearch.php?q={quote(query1)}&fl[]=identifier&fl[]=title&rows=20&output=json'
r1 = requests.get(url1, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
d1 = r1.json()
docs1 = d1.get('response', {}).get('docs', [])
print(f'Test 1 (quoted): {len(docs1)} results')
for d in docs1[:3]:
    print(f'  {d.get("identifier")} -> {d.get("title","")[:60]}')

# Test 2: unquoted serial
url2 = f'https://archive.org/advancedsearch.php?q={quote(serial)}&fl[]=identifier&fl[]=title&rows=20&output=json'
r2 = requests.get(url2, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
d2 = r2.json()
docs2 = d2.get('response', {}).get('docs', [])
print(f'\nTest 2 (unquoted): {len(docs2)} results')
for d in docs2[:3]:
    print(f'  {d.get("identifier")} -> {d.get("title","")[:60]}')

# Test 3: check matching logic
print(f'\nMatching check:')
for d in docs1[:5]:
    identifier = d.get('identifier', '')
    title = d.get('title', '')
    match = serial.lower() in title.lower() or serial.lower() in identifier.lower()
    print(f'  {identifier}: serial in title={serial.lower() in title.lower()}, in id={serial.lower() in identifier.lower()}, match={match}')

# Test 4: Try SLUS-00640 (RPG Maker - we know this has results)
serial2 = 'SLUS-00640'
query2 = f'"{serial2}"'
url3 = f'https://archive.org/advancedsearch.php?q={quote(query2)}&fl[]=identifier&fl[]=title&rows=20&output=json'
r3 = requests.get(url3, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
d3 = r3.json()
docs3 = d3.get('response', {}).get('docs', [])
print(f'\nTest 4 (SLUS-00640): {len(docs3)} results')
for d in docs3[:5]:
    identifier = d.get('identifier', '')
    title = d.get('title', '')
    match = serial2.lower() in title.lower() or serial2.lower() in identifier.lower()
    print(f'  {identifier}: match={match} -> {title[:60]}')
