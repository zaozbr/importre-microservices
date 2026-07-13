"""Testa rapidamente quais sites de ROM estao online e respondem."""
import requests
import time
from urllib.parse import quote_plus

SITES_TO_TEST = [
    ("archive_org", "https://archive.org/metadata/psx_bublbobl", "GET"),
    ("archive_org_jp", "https://archive.org/metadata/psx_bublbobl", "GET"),
    ("coolrom", "https://www.coolrom.com/roms/psx/", "GET"),
    ("blueroms", "https://www.blueroms.ws/psx/", "GET"),
    ("retrostic", "https://www.retrostic.com/", "GET"),
    ("romulation", "https://www.romulation.org/roms/PSX", "GET"),
    ("retroiso", "https://retroiso.com/", "GET"),
    ("romsretro", "https://romsretro.com/", "GET"),
    ("cdromance", "https://cdromance.org/", "GET"),
    ("vimm", "https://vimm.net/vault/?p=PS1", "GET"),
    ("romspedia", "https://www.romspedia.com/", "GET"),
    ("romsfun", "https://www.romsfun.com/", "GET"),
    ("romhustler", "https://www.romhustler.org/", "GET"),
    ("romsbase", "https://www.romsbase.com/", "GET"),
    ("hexrom", "https://hexrom.com/", "GET"),
    ("consoleroms", "https://www.consoleroms.com/", "GET"),
    ("romsgames", "https://www.romsgames.com/", "GET"),
    ("retromania", "https://www.retromania.com/", "GET"),
    ("romsdl", "https://www.romsdl.com/", "GET"),
    ("emuparadise", "https://www.emuparadise.me/", "GET"),
    ("romspack", "https://www.romspack.com/", "GET"),
    ("romspure", "https://romspure.cc/", "GET"),
    ("roms2000", "https://www.roms2000.com/", "GET"),
    ("classicgames", "https://www.classicgames.com/", "GET"),
    ("freeroms", "https://www.freeroms.com/", "GET"),
    ("romulation_org", "https://www.romulation.org/roms/PSX", "GET"),
    ("retrogames_games", "https://retrogames.games/", "GET"),
    ("retrogames_cc", "https://retrogames.cc/", "GET"),
    ("playretrogames", "https://www.playretrogames.com/", "GET"),
    ("oldiesnest", "https://www.oldiesnest.com/", "GET"),
    # Bing e DuckDuckGo para busca genérica
    ("bing", "https://www.bing.com/search?q=psx+rom+download", "GET"),
    ("ddg_lite", "https://lite.duckduckgo.com/lite/?q=psx+rom+download", "GET"),
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

results = []
for site_key, url, method in SITES_TO_TEST:
    t0 = time.time()
    try:
        r = requests.get(url, timeout=8, headers=headers, allow_redirects=True)
        ms = (time.time() - t0) * 1000
        ok = r.status_code == 200
        size = len(r.text)
        results.append((site_key, ok, r.status_code, ms, size))
        status = "OK" if ok else f"HTTP {r.status_code}"
        print(f"  {site_key:25s} {status:10s} {ms:7.0f}ms  {size:7d}B")
    except Exception as e:
        ms = (time.time() - t0) * 1000
        results.append((site_key, False, 0, ms, 0))
        err = str(e)[:60]
        print(f"  {site_key:25s} FALHOU     {ms:7.0f}ms  {err}")

online = [r[0] for r in results if r[1]]
offline = [r[0] for r in results if not r[1]]
print(f"\nOnline ({len(online)}): {online}")
print(f"Offline ({len(offline)}): {offline}")
