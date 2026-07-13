"""Testa conectividade com varios sites."""
import requests, time

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

sites = [
    ('romspedia', 'https://romspedia.com/roms/playstation-1'),
    ('retromania', 'https://retromania.gg/roms/playstation'),
    ('romsfun', 'https://romsfun.com/'),
    ('blueroms', 'https://blueroms.ws/'),
    ('hexrom', 'https://hexrom.com/'),
    ('coolrom', 'https://coolrom.com/roms/psx/'),
    ('bing', 'https://www.bing.com/search?q=test'),
    ('github', 'https://api.github.com/search/code?q=test'),
    ('archive.org', 'https://archive.org/advancedsearch.php?q=test&output=json'),
    ('ddg', 'https://lite.duckduckgo.com/lite/'),
    ('wayback', 'http://web.archive.org/'),
    ('vimm', 'https://vimm.net/vault/PS1'),
    ('romsdl', 'https://romsdl.com/'),
    ('retrostic', 'https://retrostic.com/'),
]

for name, url in sites:
    t0 = time.time()
    try:
        r = requests.get(url, timeout=8, headers=HEADERS)
        elapsed = time.time() - t0
        print(f"  {name:15s} {r.status_code} {len(r.text):6d}b {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - t0
        err = str(e)[:60]
        print(f"  {name:15s} ERRO   {elapsed:.1f}s {err}")
