import json, sys, requests

for item_id in ["psx_yokaihan", "psx_lilprinc", "slpx-02423_202501", "psx_sentient"]:
    url = f"https://archive.org/metadata/{item_id}"
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        print(f"\n=== {item_id}: HTTP {resp.status_code} ===")
        continue
    data = resp.json()
    files = data.get("files", [])
    print(f"\n=== {item_id}: {len(files)} files ===")
    print(f"  server: {data.get('server', '?')}")
    print(f"  dir: {data.get('dir', '?')}")
    for f in files[:20]:
        name = f.get("name", "?")
        fmt = f.get("format", "?")
        size = f.get("size", "?")
        print(f"  {name} [{fmt}] {size}")
