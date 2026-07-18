import requests, json, re
from urllib.parse import quote

# Broader search strategies for items not found by serialnumber
not_found = [
    ("SLPM-86780", "Taiho Shichauzo - You're Under Arrest"),
    ("SLPM-86795", "Nankuro 4"),
    ("SLPS-01860", "Tricky Sliders"),
    ("SLPS-02379", "RockMan 6 - Shijou Saidai no Tatakai!!"),
    ("SLES-00327", "WipeOut 2097"),
    ("SLPS-01259", "Tokyo 23Ku Seifuku-Wars"),
]

for serial, title in not_found:
    clean = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
    words = [w for w in clean.split() if len(w) > 1]

    print(f"\n=== {serial}: {title} ===")

    # Try 1: title words + psxgames collection
    query1 = f'({" ".join(words[:3])}) AND collection:psxgames'
    url1 = f"https://archive.org/advancedsearch.php?q={quote(query1)}&fl[]=identifier&fl[]=title&fl[]=serialnumber&rows=10&output=json"
    resp1 = requests.get(url1, timeout=30)
    docs1 = resp1.json().get("response", {}).get("docs", [])
    print(f"  title+psxgames: {len(docs1)} results")
    for d in docs1[:5]:
        t = d.get("title", "?")
        safe_t = t.encode("ascii", "replace").decode("ascii")[:60]
        print(f"    {d.get('identifier', '?')} - {safe_t}")

    # Try 2: first word + psxgames
    if not docs1 and words:
        query2 = f'({words[0]}) AND collection:psxgames'
        url2 = f"https://archive.org/advancedsearch.php?q={quote(query2)}&fl[]=identifier&fl[]=title&fl[]=serialnumber&rows=10&output=json"
        resp2 = requests.get(url2, timeout=30)
        docs2 = resp2.json().get("response", {}).get("docs", [])
        print(f"  '{words[0]}'+psxgames: {len(docs2)} results")
        for d in docs2[:5]:
            t = d.get("title", "?")
            safe_t = t.encode("ascii", "replace").decode("ascii")[:60]
            print(f"    {d.get('identifier', '?')} - {safe_t}")

    # Try 3: title without collection filter
    if not docs1:
        query3 = f'{" ".join(words[:2])} playstation'
        url3 = f"https://archive.org/advancedsearch.php?q={quote(query3)}&fl[]=identifier&fl[]=title&rows=10&output=json"
        resp3 = requests.get(url3, timeout=30)
        docs3 = resp3.json().get("response", {}).get("docs", [])
        print(f"  '{words[:2]} playstation': {len(docs3)} results")
        for d in docs3[:5]:
            t = d.get("title", "?")
            safe_t = t.encode("ascii", "replace").decode("ascii")[:60]
            print(f"    {d.get('identifier', '?')} - {safe_t}")
