import json
import re
from pathlib import Path

SITES_PATH = Path(r"D:\roms\library\roms\_importre_state\sites.json")
CANDIDATES_PATH = Path(r"D:\roms\library\roms\_importre_state\discovery_candidates.json")
SEARCHABLE_PATH = Path(r"D:\roms\library\roms\_importre_state\discovery_searchable.json")

sites = json.loads(SITES_PATH.read_text(encoding="utf-8")) if SITES_PATH.exists() else {}
data = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8")) if CANDIDATES_PATH.exists() else {}
searchable_data = json.loads(SEARCHABLE_PATH.read_text(encoding="utf-8")) if SEARCHABLE_PATH.exists() else {}
searchable = set(searchable_data.get("searchable", []))

new_sites = {
    "classicreload": "https://www.classicreload.com",
    "classicgamezone": "https://classicgamezone.com",
    "romulation_org": "https://www.romulation.org",
    "retrogames_games": "https://retrogames.games",
    "retrogames_cc": "https://retrogames.cc",
    "playretrogames": "https://playretrogames.com",
    "playretrogames_online": "https://playretrogames.online",
    "oldiesnest": "https://oldiesnest.com",
    "retrogametalk": "https://retrogametalk.com",
}

added = 0
for key, url in new_sites.items():
    if key in sites:
        continue
    domain = url.replace("https://", "").replace("http://", "")
    has_search = domain in searchable
    sites[key] = {
        "url": url,
        "search_url": f"{url}/?s={{query}}" if has_search else f"{url}/",
        "type": "page_url",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
    }
    added += 1
    print(f"Adicionado: {key} ({domain})")

tmp = str(SITES_PATH) + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(sites, f, ensure_ascii=False, indent=2)
import os
os.replace(tmp, str(SITES_PATH))
print(f"Total adicionado: {added}")
