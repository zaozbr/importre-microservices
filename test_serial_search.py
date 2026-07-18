import requests, json, re
from urllib.parse import quote

# Search by serialnumber field
test_serials = [
    "SCUS-94110",
    "SLPM-86780",
    "SLPM-86795",
    "SLPS-01860",
    "SLPM-86857",
    "SLPS-02376",
    "SLPS-02379",
    "SLPS-02423",
    "SLUS-00510",
    "SLES-00327",
    "SLPM-86021",
    "SLPS-01259",
]

for serial in test_serials:
    # Try 1: serialnumber field
    query = f"serialnumber:{quote(serial)}"
    url = f"https://archive.org/advancedsearch.php?q={query}&fl[]=identifier&fl[]=title&fl[]=serialnumber&rows=10&output=json"
    resp = requests.get(url, timeout=30)
    data = resp.json()
    docs = data.get("response", {}).get("docs", [])
    print(f"\n  serialnumber:{serial} -> {len(docs)} results")
    for d in docs[:3]:
        title = d.get("title", "?")
        safe_title = title.encode("ascii", "replace").decode("ascii")[:60]
        sn = d.get("serialnumber", "?")
        print(f"    {d.get('identifier', '?')} - {safe_title} (serial: {sn})")

    if not docs:
        # Try 2: serialnumber without hyphen
        serial_nohyphen = serial.replace("-", "")
        query2 = f"serialnumber:{serial_nohyphen}"
        url2 = f"https://archive.org/advancedsearch.php?q={query2}&fl[]=identifier&fl[]=title&fl[]=serialnumber&rows=10&output=json"
        resp2 = requests.get(url2, timeout=30)
        docs2 = resp2.json().get("response", {}).get("docs", [])
        if docs2:
            print(f"  serialnumber:{serial_nohyphen} -> {len(docs2)} results")
            for d in docs2[:3]:
                title = d.get("title", "?")
                safe_title = title.encode("ascii", "replace").decode("ascii")[:60]
                print(f"    {d.get('identifier', '?')} - {safe_title}")

        # Try 3: just the serial as text search
        query3 = quote(f'"{serial}"')
        url3 = f"https://archive.org/advancedsearch.php?q={query3}&fl[]=identifier&fl[]=title&rows=10&output=json"
        resp3 = requests.get(url3, timeout=30)
        docs3 = resp3.json().get("response", {}).get("docs", [])
        if docs3:
            print(f'  text:"{serial}" -> {len(docs3)} results')
            for d in docs3[:3]:
                title = d.get("title", "?")
                safe_title = title.encode("ascii", "replace").decode("ascii")[:60]
                print(f"    {d.get('identifier', '?')} - {safe_title}")
