import requests

# Testar metadata do archive.org
identifier = "simple-1500-series-vol-35-the-shooting-shooter-space-shot-slps-02757"
for url in [f"http://archive.org/metadata/{identifier}", f"https://archive.org/metadata/{identifier}"]:
    try:
        print(f"Trying {url}")
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        print(f"  Status: {r.status_code}, len: {len(r.text)}")
    except Exception as e:
        print(f"  Erro: {e}")
