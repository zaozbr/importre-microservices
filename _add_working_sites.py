"""Adiciona sites que funcionam ao sites.json."""
import json
from pathlib import Path

SITES_PATH = Path(r"D:\roms\library\roms\_importre_state\sites.json")

with open(SITES_PATH, "r", encoding="utf-8") as f:
    sites = json.load(f)

# Sites que responderam 200 no diagnostico
NEW_SITES = {
    "coolrom": {
        "url": "https://www.coolrom.com",
        "search_url": "https://www.coolrom.com/search/?q={query}",
        "type": "coolrom",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
        "priority": 4,
    },
    "retrostic": {
        "url": "https://www.retrostic.com",
        "search_url": "https://www.retrostic.com/search?q={query}",
        "type": "retrostic",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
        "priority": 5,
    },
    "romulation": {
        "url": "https://romulation.org",
        "search_url": "https://romulation.org/psx/?q={query}",
        "type": "direct_search",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
        "priority": 6,
    },
    "myrient": {
        "url": "https://myrient.erista.me",
        "search_url": "https://myrient.erista.me/files/Redump/Sony%20-%20PlayStation/?q={query}",
        "type": "direct_search",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
        "priority": 3,
    },
    "retroiso": {
        "url": "https://retroiso.com",
        "search_url": "https://retroiso.com/search?q={query}",
        "type": "direct_search",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 30,
        "priority": 7,
    },
    "psxdatacenter_jp": {
        "url": "https://psxdatacenter.com",
        "search_url": "",
        "type": "psxdatacenter_jp",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 30,
        "priority": 8,
    },
    "retrostic_jp": {
        "url": "https://www.retrostic.com",
        "search_url": "",
        "type": "retrostic_jp",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 30,
        "priority": 9,
    },
    "archive_org_jp": {
        "url": "https://archive.org",
        "search_url": "",
        "type": "archive_org_jp",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
        "priority": 2,
    },
    "homebrew": {
        "url": "https://archive.org",
        "search_url": "",
        "type": "homebrew",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 30,
        "priority": 10,
    },
}

for key, config in NEW_SITES.items():
    if key not in sites or not sites[key].get("enabled"):
        sites[key] = config
        print(f"  ADICIONADO/REATIVADO: {key}")
    else:
        print(f"  OK: {key} ja ativo")

with open(SITES_PATH, "w", encoding="utf-8") as f:
    json.dump(sites, f, indent=2, ensure_ascii=False)

print("\nResumo:")
enabled = [k for k, v in sites.items() if v.get("enabled")]
print(f"  Sites ativos ({len(enabled)}): {enabled}")
