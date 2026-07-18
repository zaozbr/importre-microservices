import requests, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

session = requests.Session()
session.headers.update(HEADERS)

# Visit game page first
r = session.get('https://vimm.net/vault/6455', timeout=30)
print(f'Game page: {r.status_code}')

time.sleep(5)

# Try download with GET
r2 = session.get('https://dl3.vimm.net/?mediaId=5252', 
    headers={'Referer': 'https://vimm.net/vault/6455'},
    stream=True, timeout=60)
print(f'Download: {r2.status_code}, Content-Type: {r2.headers.get("content-type","?")}')
print(f'Content-Disposition: {r2.headers.get("content-disposition","?")}')

if r2.status_code == 200 and 'x-7z' in r2.headers.get('content-type', ''):
    print('SUCCESS - rate limit reset!')
elif r2.status_code == 429:
    print('Still rate limited')
    # Try with different approach - new session, different UA
    time.sleep(10)
    session2 = requests.Session()
    session2.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    # Visit game page first
    r3 = session2.get('https://vimm.net/vault/6455', timeout=30)
    print(f'Game page (Firefox UA): {r3.status_code}')
    time.sleep(5)
    r4 = session2.get('https://dl3.vimm.net/?mediaId=5252',
        headers={'Referer': 'https://vimm.net/vault/6455'},
        stream=True, timeout=60)
    print(f'Download (Firefox UA): {r4.status_code}, Content-Type: {r4.headers.get("content-type","?")}')
