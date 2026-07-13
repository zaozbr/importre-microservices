"""Diagnostico completo: testa conectividade de buscadores e sites de ROM."""
import requests
import time
import json
from urllib.parse import quote_plus

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
}

# 1. Buscadores
print("=== BUSCADORES ===")
engines = [
    ("Google", "https://www.google.com/search?q=test&num=5"),
    ("Google BR", "https://www.google.com.br/search?q=test&num=5"),
    ("Bing", "https://www.bing.com/search?q=test"),
    ("DuckDuckGo HTML", "https://html.duckduckgo.com/html/?q=test"),
    ("DuckDuckGo lite", "https://lite.duckduckgo.com/lite/?q=test"),
    ("Yandex", "https://yandex.com/search/?text=test"),
    ("Brave", "https://search.brave.com/search?q=test"),
    ("Startpage", "https://www.startpage.com/sp/search?query=test"),
]
for name, url in engines:
    try:
        t0 = time.time()
        resp = requests.get(url, timeout=10, headers=HEADERS, allow_redirects=True)
        elapsed = time.time() - t0
        has_captcha = "captcha" in resp.text.lower() or "unusual traffic" in resp.text.lower()
        print(f"  {name:20s} HTTP {resp.status_code} ({elapsed:.1f}s) captcha={has_captcha} len={len(resp.text)}")
    except Exception as e:
        print(f"  {name:20s} ERRO: {str(e)[:100]}")

# 2. Sites de ROM
print("\n=== SITES DE ROM ===")
rom_sites = [
    ("archive.org", "https://archive.org/advancedsearch.php?q=SLUS-00592&output=json&rows=1"),
    ("coolrom.com", "https://www.coolrom.com/roms/psx/"),
    ("vimm.net", "https://vimm.net/vault/PS1"),
    ("cdromance.org", "https://cdromance.org/psx-iso/"),
    ("romspedia.com", "https://www.romspedia.com/roms/playstation"),
    ("retrostic.com", "https://www.retrostic.com/roms/ps-1"),
    ("romsdl.net", "https://romsdl.net/psx"),
    ("blueroms.com", "https://blueroms.com/psx"),
    ("romsretro.com", "https://www.romsretro.com/psx"),
    ("romsgames.net", "https://www.romsgames.net/psx"),
    ("retromania.gg", "https://retromania.gg/psx"),
    ("hexrom.net", "https://hexrom.net/psx"),
    ("consoleroms.com", "https://www.consoleroms.com/psx"),
    ("romulation.org", "https://romulation.org/psx"),
    ("myrient.erista.me", "https://myrient.erista.me/files/Redump/Sony%20-%20PlayStation/"),
    ("edgeemu.net", "https://edgeemu.net/ps1"),
    ("psxdatacenter.com", "https://psxdatacenter.com/"),
]
for name, url in rom_sites:
    try:
        t0 = time.time()
        resp = requests.get(url, timeout=15, headers=HEADERS, allow_redirects=True)
        elapsed = time.time() - t0
        blocked = resp.status_code in (403, 451, 429)
        print(f"  {name:25s} HTTP {resp.status_code} ({elapsed:.1f}s) blocked={blocked} len={len(resp.text)}")
    except Exception as e:
        print(f"  {name:25s} ERRO: {str(e)[:100]}")

# 3. Testar busca real no Bing por SLUS-00592
print("\n=== TESTE BING: SLUS-00592 ===")
try:
    bing_q = quote_plus('"SLUS-00592" psx rom download')
    url = f"https://www.bing.com/search?q={bing_q}&count=20"
    resp = requests.get(url, timeout=15, headers=HEADERS)
    print(f"  HTTP {resp.status_code} len={len(resp.text)}")
    # Extrair URLs de sites conhecidos
    import re
    known = ["archive.org", "coolrom.com", "vimm.net", "cdromance.org", "romspedia.com",
             "retrostic.com", "romsdl.net", "blueroms.com", "romsretro.com", "romsgames.net",
             "retromania.gg", "hexrom.net", "consoleroms.com", "romulation.org",
             "myrient.erista.me", "edgeemu.net"]
    for domain in known:
        pattern = rf'https?://(?:www\.)?{re.escape(domain)}/[^"\'<>\s]+'
        matches = re.findall(pattern, resp.text, re.IGNORECASE)
        if matches:
            print(f"  {domain}: {matches[:3]}")
except Exception as e:
    print(f"  ERRO: {e}")
