import json
from pathlib import Path

SITES_PATH = Path(r"D:\roms\library\roms\_importre_state\sites.json")

sites = json.loads(SITES_PATH.read_text(encoding="utf-8")) if SITES_PATH.exists() else {}

new_sites = {
    "emuparadise": {
        "url": "https://www.emuparadise.me",
        "search_url": "https://www.emuparadise.me/roms/search.php?query={query}&system=Sony+Playstation",
        "type": "page_url",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "myrient": {
        "url": "https://myrient.erista.me",
        "search_url": "https://myrient.erista.me/files/Internet%20Archive/chadmaster/chd_psx/",
        "type": "direct_search",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "romspack": {
        "url": "https://www.romspack.com",
        "search_url": "https://www.romspack.com/?s={query}",
        "type": "page_url",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "totalroms": {
        "url": "https://www.totalroms.com",
        "search_url": "https://www.totalroms.com/?s={query}",
        "type": "page_url",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "romspure": {
        "url": "https://romspure.cc",
        "search_url": "https://romspure.cc/search?q={query}",
        "type": "page_url",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "retrobit": {
        "url": "https://retro-bit.ru",
        "search_url": "https://retro-bit.ru/?s={query}",
        "type": "page_url",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "roms2000": {
        "url": "https://roms2000.com",
        "search_url": "https://roms2000.com/?s={query}",
        "type": "page_url",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "classicgames": {
        "url": "https://classicgames.me",
        "search_url": "https://classicgames.me/?s={query}",
        "type": "page_url",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
    "freeroms": {
        "url": "https://www.freeroms.com",
        "search_url": "https://www.freeroms.com/psx.htm",
        "type": "page_url",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    },
}

added = 0
for key, cfg in new_sites.items():
    if key not in sites:
        sites[key] = cfg
        added += 1
        print(f"Adicionado: {key}")

tmp = str(SITES_PATH) + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(sites, f, ensure_ascii=False, indent=2)
import os
os.replace(tmp, str(SITES_PATH))
print(f"Total adicionado: {added}")
