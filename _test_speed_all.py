import requests, time, threading

results = {}

def test_site(name, url, headers=None, max_bytes=20*1024*1024):
    try:
        start = time.time()
        r = requests.get(url, stream=True, timeout=60, headers=headers or {})
        if r.status_code != 200:
            results[name] = (f'HTTP {r.status_code}', 0, 0)
            return
        downloaded = 0
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk:
                downloaded += len(chunk)
                if downloaded >= max_bytes:
                    break
        end = time.time()
        speed = downloaded / (end - start) / 1024
        results[name] = ('OK', downloaded, speed)
    except Exception as e:
        results[name] = (str(e)[:100], 0, 0)

# CoolROM
test_site('coolrom', 'https://dl.coolrom.com/roms/psx/DX%20Jinsei%20Game%20-%20The%20Game%20of%20Life%20%28Japan%29.7z/0KIe_rnGSf_aLaLPUnrTzN9omJ1nydzWw7dMWyDfa8c/1783740360/', {'User-Agent': 'Mozilla/5.0'})
# Archive.org - precisamos de um URL real
# Vimm
# test_site('vimm', 'https://archival.cat/PS1/5745.7z', {'User-Agent': 'Mozilla/5.0'})
# Teste genérico
# test_site('google', 'https://www.google.com', {'User-Agent': 'Mozilla/5.0'}, max_bytes=100*1024)

print(f"coolrom: {results.get('coolrom')}")
