import sys, time, requests, urllib.parse, re
from bs4 import BeautifulSoup

name = 'Celeste Classic PSX'
req_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

t0 = time.time()
search_terms = [
    f'"{name}" ps1 homebrew download',
    f'"{name}" psx homebrew download',
    f'"{name}" ps1 homebrew rom',
    f'"{name}" psx homebrew bin',
    f'{name} ps1 homebrew',
]
for ddg_query in search_terms:
    ddg_url = f'https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(ddg_query)}'
    print(f'[{(time.time()-t0):.1f}s] Buscando: {ddg_query}')
    resp = requests.get(ddg_url, timeout=15, headers=req_headers)
    print(f'[{(time.time()-t0):.1f}s] status: {resp.status_code}')
    if resp.status_code not in (200, 202):
        continue
    soup = BeautifulSoup(resp.text, 'lxml')
    results = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        real_url = None
        if 'uddg=' in href:
            real_url = urllib.parse.unquote(href.split('uddg=')[1].split('&')[0])
        elif href.startswith('http') and 'duckduckgo' not in href:
            real_url = href
        if real_url and text and len(text) > 3 and 'duckduckgo' not in real_url.lower():
            results.append((real_url, text))
    print(f'[{(time.time()-t0):.1f}s] results: {len(results)}')
    for u, t in results[:5]:
        print(f'  {u[:80]} | {t[:40]}')
    # Sites comuns
    known_domains = {
        'itch.io': 'itch.io',
        'github.com': 'github.com',
        'archive.org': 'archive.org',
    }
    urls_found = []
    for url, text in results:
        domain = urllib.parse.urlparse(url).netloc.lower().replace('www.', '')
        for known, key in known_domains.items():
            if known in domain:
                urls_found.append((key, url))
                break
    print(f'[{(time.time()-t0):.1f}s] urls_found: {len(urls_found)}')
    for key, url in urls_found[:5]:
        print(f'  {key}: {url[:80]}')
    for site_key, url in urls_found[:8]:
        print(f'[{(time.time()-t0):.1f}s] Tentando {site_key}: {url[:80]}')
        try:
            if site_key == 'itch.io':
                r2 = requests.get(url, timeout=10, headers=req_headers, allow_redirects=True)
                print(f'  itch page status: {r2.status_code}')
                soup2 = BeautifulSoup(r2.text, 'lxml')
                upload_id = None
                for tag in soup2.find_all(attrs={'data-upload_id': True}):
                    upload_id = tag.get('data-upload_id')
                    break
                csrf = ''
                for meta in soup2.find_all('meta'):
                    if meta.get('name') == 'csrf-token':
                        csrf = meta.get('content', '')
                print(f'  upload_id: {upload_id}, csrf: {csrf[:20]}')
                if upload_id and csrf:
                    post_url = url.rstrip('/') + '/download_url'
                    r3 = requests.post(post_url, data={'csrf_token': csrf, 'upload_id': upload_id}, timeout=10, headers={**req_headers, 'X-Requested-With': 'XMLHttpRequest', 'Referer': url})
                    print(f'  post status: {r3.status_code}, text: {r3.text[:100]}')
                    if r3.status_code == 200:
                        try:
                            data = r3.json()
                            dl_url = data.get('url', '')
                        except:
                            dl_url = r3.text.strip()
                        print(f'  dl_url: {dl_url[:80]}')
                        if dl_url.startswith('http'):
                            r4 = requests.get(dl_url, timeout=10, headers=req_headers, stream=True)
                            ct = r4.headers.get('content-type', '')
                            print(f'  dl status: {r4.status_code}, ct: {ct}, url: {r4.url[:80]}')
                            if ct.startswith('application/') or any(r4.url.lower().endswith(ext) for ext in ['.zip', '.7z', '.rar']):
                                print('  SUCESSO direct_url')
                                break
                            print('  retorna page_url')
                            break
        except Exception as e:
            print(f'  erro: {e}')
print(f'[{(time.time()-t0):.1f}s] fim')
