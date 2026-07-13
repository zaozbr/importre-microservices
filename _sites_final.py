"""Reescreve sites.json com TODOS os sites online (26+ sites)."""
import json
from pathlib import Path

SITES_PATH = Path(r"D:\roms\library\roms\_importre_state\sites.json")

sites = {
    # === Sites primarios ===
    "archive_org": {"url": "http://archive.org", "search_url": "", "type": "archive_org",
        "enabled": True, "fail_count": 0, "max_fails": 100, "priority": 1},
    "archive_org_jp": {"url": "http://archive.org", "search_url": "", "type": "archive_org_jp",
        "enabled": True, "fail_count": 0, "max_fails": 100, "priority": 2},
    "coolrom": {"url": "https://www.coolrom.com", "search_url": "https://www.coolrom.com/search/?q={query}",
        "type": "coolrom", "enabled": True, "fail_count": 0, "max_fails": 50, "priority": 3},
    "romulation": {"url": "https://www.romulation.org", "search_url": "https://www.romulation.org/roms/PSX?q={query}",
        "type": "romulation", "enabled": True, "fail_count": 0, "max_fails": 50, "priority": 4},
    "retrostic": {"url": "https://www.retrostic.com", "search_url": "https://www.retrostic.com/search?q={query}",
        "type": "retrostic", "enabled": True, "fail_count": 0, "max_fails": 50, "priority": 5},
    "retroiso": {"url": "https://retroiso.com", "search_url": "https://retroiso.com/search?q={query}",
        "type": "retroiso", "enabled": True, "fail_count": 0, "max_fails": 50, "priority": 6},
    # === Sites secundarios ===
    "romsretro": {"url": "https://romsretro.com", "search_url": "https://romsretro.com/?s={query}",
        "type": "romsretro", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 7},
    "romspedia": {"url": "https://www.romspedia.com", "search_url": "https://www.romspedia.com/?s={query}",
        "type": "romspedia", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 8},
    "romsfun": {"url": "https://www.romsfun.com", "search_url": "https://www.romsfun.com/?s={query}",
        "type": "romsfun", "enabled": False, "fail_count": 999, "priority": 0},
    "romhustler": {"url": "https://www.romhustler.org", "search_url": "https://www.romhustler.org/?s={query}",
        "type": "romhustler", "enabled": False, "fail_count": 999, "priority": 0},
    "romsbase": {"url": "https://www.romsbase.com", "search_url": "https://www.romsbase.com/roms/playstation?q={query}",
        "type": "romsbase", "enabled": False, "fail_count": 999, "priority": 0},
    "hexrom": {"url": "https://hexrom.com", "search_url": "https://hexrom.com/?s={query}",
        "type": "hexrom", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 12},
    "consoleroms": {"url": "https://www.consoleroms.com", "search_url": "https://www.consoleroms.com/?s={query}",
        "type": "consoleroms", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 13},
    "romsgames": {"url": "https://www.romsgames.com", "search_url": "https://www.romsgames.com/?s={query}",
        "type": "romsgames", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 14},
    "retromania": {"url": "https://www.retromania.com", "search_url": "https://www.retromania.com/?s={query}",
        "type": "retromania", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 15},
    "romsdl": {"url": "https://www.romsdl.com", "search_url": "https://www.romsdl.com/?s={query}",
        "type": "romsdl", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 16},
    "emuparadise": {"url": "https://www.emuparadise.me", "search_url": "https://www.emuparadise.me/roms/search.php?query={query}&system=Sony+Playstation",
        "type": "emuparadise", "enabled": False, "fail_count": 999, "priority": 0},
    "romspure": {"url": "https://romspure.cc", "search_url": "https://romspure.cc/?s={query}",
        "type": "romspure", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 18},
    "roms2000": {"url": "https://www.roms2000.com", "search_url": "https://www.roms2000.com/?s={query}",
        "type": "roms2000", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 19},
    "classicgames": {"url": "https://www.classicgames.com", "search_url": "https://www.classicgames.com/?s={query}",
        "type": "classicgames", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 20},
    "retrogames_games": {"url": "https://retrogames.games", "search_url": "https://retrogames.games/?s={query}",
        "type": "retrogames_games", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 21},
    "retrogames_cc": {"url": "https://retrogames.cc", "search_url": "https://retrogames.cc/?s={query}",
        "type": "retrogames_cc", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 22},
    "playretrogames": {"url": "https://www.playretrogames.com", "search_url": "https://www.playretrogames.com/?s={query}",
        "type": "playretrogames", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 23},
    "oldiesnest": {"url": "https://www.oldiesnest.com", "search_url": "https://www.oldiesnest.com/?s={query}",
        "type": "oldiesnest", "enabled": True, "fail_count": 0, "max_fails": 30, "priority": 24},
    # === Sites JP especificos ===
    "psxdatacenter_jp": {"url": "https://psxdatacenter.com", "search_url": "", "type": "psxdatacenter_jp",
        "enabled": True, "fail_count": 0, "max_fails": 50, "priority": 25},
    "retrostic_jp": {"url": "https://www.retrostic.com", "search_url": "", "type": "retrostic_jp",
        "enabled": True, "fail_count": 0, "max_fails": 50, "priority": 26},
    "homebrew": {"url": "http://archive.org", "search_url": "", "type": "homebrew",
        "enabled": True, "fail_count": 0, "max_fails": 50, "priority": 27},
    "google": {"url": "https://www.bing.com", "search_url": "", "type": "google",
        "enabled": True, "fail_count": 0, "max_fails": 100, "priority": 28},
    # === Sites banidos (offline) ===
    "blueroms": {"url": "https://www.blueroms.ws", "enabled": False, "fail_count": 999, "priority": 0},
    "cdromance": {"url": "https://cdromance.org", "enabled": False, "fail_count": 999, "priority": 0},
    "vimm": {"url": "https://vimm.net", "enabled": False, "fail_count": 999, "priority": 0},
    "romspack": {"url": "https://www.romspack.com", "enabled": False, "fail_count": 999, "priority": 0},
    "freeroms": {"url": "https://www.freeroms.com", "enabled": False, "fail_count": 999, "priority": 0},
    "myrient": {"url": "https://myrient.erista.me", "enabled": False, "fail_count": 999, "priority": 0},
}

with open(SITES_PATH, "w", encoding="utf-8") as f:
    json.dump(sites, f, indent=2, ensure_ascii=False)

enabled = [k for k, v in sites.items() if v.get("enabled")]
print(f"Sites ativos ({len(enabled)}): {enabled}")
