import requests, json

# Test download URLs
tests = [
    ("psx_sentient", "playstationdisc.chd"),
    ("psx_yokaihan", "playstationdisc.chd"),
    ("slpx-02423_202501", "SLPX-02423.ISO"),
]

for identifier, filename in tests:
    # Format 1: archive.org/download/ (no server)
    url1 = f"https://archive.org/download/{identifier}/{filename}"
    # Format 2: with server prefix
    meta_url = f"https://archive.org/metadata/{identifier}"
    resp = requests.get(meta_url, timeout=30)
    data = resp.json()
    server = data.get("server", "")
    dir_path = data.get("dir", "")
    url2 = f"https://{server}{dir_path}/{filename}" if server else ""

    print(f"\n=== {identifier}/{filename} ===")
    print(f"  server: {server}, dir: {dir_path}")

    # Test URL 1 (HEAD request)
    try:
        r = requests.head(url1, timeout=30, allow_redirects=True)
        print(f"  URL1 (archive.org/download/): HTTP {r.status_code}, Content-Length: {r.headers.get('content-length', '?')}")
    except Exception as e:
        print(f"  URL1 error: {e}")

    # Test URL 2 (server prefix)
    if url2:
        try:
            r = requests.head(url2, timeout=30, allow_redirects=True)
            print(f"  URL2 (server prefix): HTTP {r.status_code}, Content-Length: {r.headers.get('content-length', '?')}")
        except Exception as e:
            print(f"  URL2 error: {e}")

# Also test: does the search by serial work for JP titles?
print("\n\n=== Search tests ===")
for serial in ["SLPM-86780", "SLPM-86795", "SLPS-01860", "SCUS-94110"]:
    # Try quoted serial
    url = f'https://archive.org/advancedsearch.php?q="{serial}"&fl[]=identifier&fl[]=title&rows=10&output=json'
    resp = requests.get(url, timeout=30)
    data = resp.json()
    docs = data.get("response", {}).get("docs", [])
    print(f'\n  "{serial}": {len(docs)} results')
    for d in docs[:5]:
        print(f"    {d.get('identifier', '?')} - {d.get('title', '?')[:60]}")

    # Try without hyphen
    serial_nohyphen = serial.replace("-", "")
    url2 = f'https://archive.org/advancedsearch.php?q="{serial_nohyphen}"&fl[]=identifier&fl[]=title&rows=10&output=json'
    resp2 = requests.get(url2, timeout=30)
    data2 = resp2.json()
    docs2 = data2.get("response", {}).get("docs", [])
    if docs2:
        print(f'  "{serial_nohyphen}": {len(docs2)} results')
        for d in docs2[:3]:
            print(f"    {d.get('identifier', '?')} - {d.get('title', '?')[:60]}")
