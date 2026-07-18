import requests, re, subprocess, os, time
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Step 1: Get rom page
r = requests.get('https://www.romulation.org/rom/PSX/Vigilante-8', headers=HEADERS, timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break
print(f'Download page link: {dl_link[:80]}...')

# Step 2: Get pluto link
r2 = requests.get(dl_link, headers={**HEADERS, 'Referer': 'https://www.romulation.org/rom/PSX/Vigilante-8'}, timeout=30)
links = re.findall(r'https://pluto\.romulation\.net/files/guest/[^\s"<>]+', r2.text)
print(f'Pluto links found: {len(links)}')
if not links:
    print('No pluto links!')
    exit(1)

# Step 3: Download IMMEDIATELY
pluto_url = links[0]
dest = r'F:\downloads\psx_faltantes\SLUS-00510.rar'
if os.path.exists(dest):
    os.remove(dest)

cmd = ['curl', '-L', '-o', dest, '--connect-timeout', '30', '--max-time', '300',
       '-H', f'User-Agent: {HEADERS["User-Agent"]}',
       '-H', 'Referer: https://www.romulation.org/rom/PSX/Vigilante-8',
       '-s', '--show-error', pluto_url]

t0 = time.time()
result = subprocess.run(cmd, capture_output=True, text=True, timeout=320)
dt = time.time() - t0
print(f'Download: rc={result.returncode}, time={dt:.1f}s, stderr={result.stderr[:200]}')
if os.path.exists(dest):
    size = os.path.getsize(dest)
    print(f'File size: {size} bytes ({size/1024/1024:.1f} MB)')
    if size < 1024:
        with open(dest, 'r', errors='ignore') as f:
            print('Content:', f.read()[:300])
    else:
        print('Download SUCCESS!')
else:
    print('File not created')
