import requests, json, re
from urllib.parse import quote

# Test title-based searches for JP titles
jp_tests = [
    ("SLPM-86780", "Taiho Shichauzo - You're Under Arrest"),
    ("SLPS-01860", "Tricky Sliders"),
    ("SLPM-86795", "Nankuro 4"),
    ("SLPM-86857", "Youkai Kaasobi"),
    ("SLPS-02376", "Rhapsody 2 - Little Princess"),
    ("SLPS-02379", "RockMan 6 - Shijou Saidai no Tatakai!!"),
    ("SLPS-02423", "Parts' Dik"),
    ("SLUS-00510", "Vigilante 8"),
    ("SLES-00327", "WipeOut 2097"),
]

for serial, title in jp_tests:
    clean = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
    words = [w for w in clean.split() if len(w) > 1]

    # Try 1: title + psx
    query1 = " ".join(words[:3]) + " psx"
    url1 = f"https://archive.org/advancedsearch.php?q={quote(query1)}&fl[]=identifier&fl[]=title&rows=10&output=json"
    resp1 = requests.get(url1, timeout=30)
    docs1 = resp1.json().get("response", {}).get("docs", [])

    # Try 2: title + playstation
    query2 = " ".join(words[:3]) + " playstation"
    url2 = f"https://archive.org/advancedsearch.php?q={quote(query2)}&fl[]=identifier&fl[]=title&rows=10&output=json"
    resp2 = requests.get(url2, timeout=30)
    docs2 = resp2.json().get("response", {}).get("docs", [])

    # Try 3: just the title (no psx/playstation)
    query3 = " ".join(words[:3])
    url3 = f"https://archive.org/advancedsearch.php?q={quote(query3)}&fl[]=identifier&fl[]=title&rows=10&output=json"
    resp3 = requests.get(url3, timeout=30)
    docs3 = resp3.json().get("response", {}).get("docs", [])

    print(f"\n=== {serial}: {title} ===")
    print(f"  query1 ('{query1}'): {len(docs1)} results")
    for d in docs1[:3]:
        print(f"    {d.get('identifier', '?')} - {d.get('title', '?')[:60]}")
    print(f"  query2 ('{query2}'): {len(docs2)} results")
    for d in docs2[:3]:
        print(f"    {d.get('identifier', '?')} - {d.get('title', '?')[:60]}")
    print(f"  query3 ('{query3}'): {len(docs3)} results")
    for d in docs3[:3]:
        print(f"    {d.get('identifier', '?')} - {d.get('title', '?')[:60]}")
