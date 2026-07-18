import requests, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

session = requests.Session()
session.headers.update(HEADERS)

# Try different URL formats
urls = [
    'https://vimm.net/vault/?p=listing&search=Backyard+Football',
    'https://vimm.net/vault/?p=list&search=Backyard+Football',
    'https://vimm.net/?p=listing&search=Backyard+Football',
    'https://vimm.net/vault/SlUS-01095',
    'https://vimm.net/vault/?p=detail&search=Backyard+Football',
]

for url in urls:
    try:
        r = session.get(url, timeout=15, allow_redirects=True)
        print(f'{r.status_code} len={len(r.text):6d} {url}')
        if r.status_code == 200 and len(r.text) > 1000:
            # Check for vault links
            links = re.findall(r'/vault/(\d+)', r.text)
            if links:
                print(f'  -> Found vault IDs: {links[:5]}')
            # Check for mediaId
            mids = re.findall(r'mediaId["\s]*=["\s]*(\d+)', r.text)
            if mids:
                print(f'  -> Found mediaIds: {mids[:5]}')
            # Show title
            titles = re.findall(r'<title>(.*?)</title>', r.text, re.I)
            if titles:
                print(f'  -> Title: {titles[0][:80]}')
    except Exception as e:
        print(f'ERROR {url}: {e}')
