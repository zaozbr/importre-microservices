"""Testa quais collections são acessíveis (não requerem auth)."""
import requests, json

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

collections = [
    "Redump.orgSonyPlayStation-PAL-J",
    "redump_psx",
    "CuratedPSXRedumpCHDs",
    "psx-roms-archive",
    "Redump_PSX_2021_06_04_A_C",
    "Redump_PSX_2021_06_04_D_F",
]

for coll in collections:
    # Testar download do primeiro arquivo ROM
    url = f"http://archive.org/metadata/{coll}"
    r = s.get(url, timeout=15)
    if r.status_code != 200:
        print(f"{coll}: metadata HTTP {r.status_code}")
        continue

    data = r.json()
    files = data.get('files', [])
    rom_file = None
    for f in files:
        fname = f.get('name', '')
        if any(fname.lower().endswith(ext) for ext in ('.zip', '.7z', '.chd')):
            rom_file = fname
            break

    if not rom_file:
        print(f"{coll}: sem arquivos ROM")
        continue

    from urllib.parse import quote
    dl_url = f"http://archive.org/download/{coll}/{quote(rom_file, safe='/')}"
    r2 = s.get(dl_url, timeout=10, stream=True)
    print(f"{coll}: download {r2.status_code} ({rom_file[:40]})")
    r2.close()
