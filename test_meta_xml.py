import requests, json, re, sys
from urllib.parse import quote

# Check metadata XML for serial info
for item_id in ["psx_sentient", "psx_yokaihan", "psx_lilprinc"]:
    url = f"https://archive.org/metadata/{item_id}"
    resp = requests.get(url, timeout=30)
    data = resp.json()
    # Check metadata fields
    meta = data.get("metadata", {})
    print(f"\n=== {item_id} ===")
    for k, v in meta.items():
        if isinstance(v, str) and len(v) < 200:
            print(f"  {k}: {v}")
        elif isinstance(v, list):
            print(f"  {k}: {v[:3]}")

# Now try: search for all items with identifier starting with "psx_"
print("\n\n=== Search: identifier:(psx_*) ===")
url = "https://archive.org/advancedsearch.php?q=identifier%3Apsx_*&fl[]=identifier&fl[]=title&sort[]=identifierSort&rows=50&output=json"
resp = requests.get(url, timeout=30)
data = resp.json()
docs = data.get("response", {}).get("docs", [])
print(f"Total psx_* items: {data.get('response', {}).get('numFound', '?')}")
for d in docs[:20]:
    title = d.get("title", "?")
    # Safe encode for Windows console
    safe_title = title.encode("ascii", "replace").decode("ascii")[:60]
    print(f"  {d.get('identifier', '?')} - {safe_title}")

# Try searching by game name with psx_ prefix pattern
print("\n\n=== Search: psx_ + title word ===")
test_titles = [
    ("SLPS-01860", "Tricky Sliders"),
    ("SLPS-02423", "Parts Dik"),
    ("SLPS-02379", "RockMan 6"),
    ("SLUS-00510", "Vigilante 8"),
    ("SLES-00327", "WipeOut 2097"),
]
for serial, title in test_titles:
    clean = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
    first_word = clean.split()[0].lower() if clean.split() else ""
    query = f"identifier:(psx_{first_word}*)"
    url = f"https://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&fl[]=title&rows=10&output=json"
    resp = requests.get(url, timeout=30)
    docs = resp.json().get("response", {}).get("docs", [])
    print(f"\n  {serial} '{title}' -> identifier:(psx_{first_word}*): {len(docs)} results")
    for d in docs[:5]:
        t = d.get("title", "?")
        safe_t = t.encode("ascii", "replace").decode("ascii")[:60]
        print(f"    {d.get('identifier', '?')} - {safe_t}")
