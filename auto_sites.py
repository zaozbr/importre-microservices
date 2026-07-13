#!/usr/bin/env python3
"""
auto_sites.py — Sistema de autoimplementação de sites de ROMs PSX.

Funcionalidades:
1. Procurar novos sites de ROMs PSX via web search
2. Testar acessibilidade e estrutura
3. Detectar padrões de busca e download
4. Gerar função de search automaticamente
5. Adicionar ao sites.json

Uso:
    python auto_sites.py --discover   # Descobrir novos sites
    python auto_sites.py --test       # Testar sites conhecidos
    python auto_sites.py --implement  # Implementar sites detectados
"""
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, quote_plus, urlparse

STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
SITES_PATH = STATE_DIR / "sites.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Sites conhecidos para nao redescobrir
KNOWN_SITES = {
    "archive.org", "coolrom.com", "retrostic.com", "romsdl.com",
    "vimm.net", "cdromance.org", "romulation.org", "emuparadise.me",
    "edgeemu.net", "romspure.cc", "romsplanet.com", "myrient.erista.me",
    "hexrom.com", "romsfun.com", "romspedia.com", "wowroms.com",
    "freeroms.com", "romhustler.org", "emulatorgames.net", "romsgames.net",
    "consoleroms.com", "retromania.gg", "romsretro.com", "psxrenzukoken.com"
}

# Lista de sites candidatos para testar (encontrados via pesquisa)
CANDIDATE_SITES = [
    # Sites que podem ter PSX ROMs
    ("romsfun.com", "https://romsfun.com/roms/playstation/"),
    ("hexrom.com", "https://hexrom.com/roms/playstation/"),
    ("romspedia.com", "https://www.romspedia.com/roms/playstation-1"),
    ("wowroms.com", "https://wowroms.com/en/roms/list/Playstation"),
    ("freeroms.com", "https://www.freeroms.com/psx.htm"),
    ("romhustler.org", "https://romhustler.org/roms/psx"),
    ("emulatorgames.net", "https://www.emulatorgames.net/roms/playstation/"),
    ("romsgames.net", "https://www.romsgames.net/roms/playstation/"),
    ("consoleroms.com", "https://www.consoleroms.com/roms/psx"),
    ("retromania.gg", "https://retromania.gg/roms/playstation"),
    ("romsretro.com", "https://romsretro.com/roms/psx/"),
    ("psxrenzukoken.com", "https://www.psxrenzukoken.com/nk2/downloads/"),
    # Novos sites para explorar
    ("loveroms.com", "https://www.loveroms.com/roms/playstation"),
    ("gamelooper.com", "https://gamelooper.com/roms/playstation"),
    ("romsdownload.net", "https://romsdownload.net/roms/playstation"),
    ("romulation.net", "https://www.romulation.org/roms/PSX"),
    ("portalroms.com", "https://www.portalroms.com/roms/playstation"),
    ("romsever.com", "https://romsever.com/roms/playstation"),
    ("cdromance.org", "https://cdromance.org/roms/psx/"),
    ("psxdatacenter.com", "https://psxdatacenter.com/"),
]


def test_site_accessibility(name, url):
    """Testa se o site é acessível e retorna informações sobre a estrutura."""
    result = {
        "name": name,
        "url": url,
        "accessible": False,
        "status_code": None,
        "has_psx": False,
        "has_search": False,
        "has_serials": False,
        "has_jp": False,
        "has_eur": False,
        "download_pattern": None,
        "search_pattern": None,
        "game_links": [],
        "error": None,
    }
    try:
        resp = requests.get(url, timeout=20, headers=HEADERS, allow_redirects=True)
        result["status_code"] = resp.status_code
        result["accessible"] = resp.status_code == 200
        if not result["accessible"]:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        soup = BeautifulSoup(resp.text, "lxml")

        # Verificar se tem jogos de PSX
        game_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not text or len(text) < 3:
                continue
            # Procurar links que parecem paginas de jogo
            if any(kw in href.lower() for kw in ["/roms/", "/rom/", "/game/", "/iso/", "/psx/", "/playstation"]):
                if any(kw in text.lower() for kw in ["iso", "rom", "psx", "ps1", "playstation"]):
                    game_links.append((href, text))
        result["game_links"] = game_links[:10]
        result["has_psx"] = len(game_links) > 0

        # Verificar se tem seriais visiveis
        serial_pattern = re.compile(r"[A-Z]{4}-\d{3,6}")
        for _, text in game_links:
            if serial_pattern.search(text):
                result["has_serials"] = True
                break
            # Tambem verificar no href
            if serial_pattern.search(href.replace("-", "").replace("_", "")):
                result["has_serials"] = True
                break

        # Verificar se tem jogos JP e EUR
        for _, text in game_links:
            tl = text.lower()
            if "(japan)" in tl or "(j)" in tl or "slps" in tl or "scps" in tl or "slpm" in tl:
                result["has_jp"] = True
            if "(europe)" in tl or "(e)" in tl or "sles" in tl or "sces" in tl:
                result["has_eur"] = True

        # Verificar se tem busca
        for form in soup.find_all("form"):
            action = form.get("action", "")
            method = form.get("method", "").lower()
            if method == "get" or "search" in action.lower():
                result["has_search"] = True
                result["search_pattern"] = action
                break
        # Procurar campo de busca
        for inp in soup.find_all("input"):
            if inp.get("type") == "search" or "search" in (inp.get("name", "") + inp.get("id", "")).lower():
                result["has_search"] = True
                break

        # Detectar padrao de download
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(href.endswith(ext) for ext in [".zip", ".7z", ".iso", ".bin", ".chd"]):
                result["download_pattern"] = "direct"
                break
            if "download" in href.lower():
                result["download_pattern"] = "download_page"
                break

    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"connection error: {str(e)[:100]}"
    except Exception as e:
        result["error"] = str(e)[:200]
    return result


def test_site_download(name, base_url, game_link):
    """Testa se é possível baixar um jogo do site."""
    href, text = game_link
    full_url = urljoin(base_url, href)
    try:
        resp = requests.get(full_url, timeout=15, headers=HEADERS)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        soup = BeautifulSoup(resp.text, "lxml")
        # Procurar link de download direto
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if any(h.endswith(ext) for ext in [".zip", ".7z", ".iso", ".bin", ".chd"]):
                dl_url = urljoin(full_url, h)
                # Testar HEAD
                try:
                    head = requests.head(dl_url, timeout=10, headers=HEADERS, allow_redirects=True)
                    if head.status_code == 200:
                        return dl_url, f"direct download: {head.headers.get('content-length', '?')} bytes"
                except:
                    pass
        # Procurar form de download
        for form in soup.find_all("form"):
            action = form.get("action", "")
            if "download" in action.lower():
                return urljoin(full_url, action), "form download"
        # Procurar redirect JS
        for script in soup.find_all("script"):
            text = script.string or ""
            match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', text)
            if match and "download" in match.group(1).lower():
                return match.group(1), "js redirect"
        # Procurar botao com data-url
        for btn in soup.find_all("button"):
            data_url = btn.get("data-url", "")
            if data_url:
                return urljoin(full_url, data_url), "button data-url"
        return None, "sem link de download"
    except Exception as e:
        return None, str(e)[:100]


def discover_sites():
    """Descobre e testa novos sites de ROMs PSX."""
    print("=" * 60)
    print("DESCOBERTA DE NOVOS SITES DE ROMs PSX")
    print("=" * 60)

    results = []
    for name, url in CANDIDATE_SITES:
        if name in KNOWN_SITES:
            print(f"\n--- {name} (conhecido) ---")
        else:
            print(f"\n--- {name} (novo) ---")
        result = test_site_accessibility(name, url)
        print(f"  Acessivel: {result['accessible']} (HTTP {result['status_code']})")
        print(f"  Tem PSX: {result['has_psx']}")
        print(f"  Tem seriais: {result['has_serials']}")
        print(f"  Tem JP: {result['has_jp']}, EUR: {result['has_eur']}")
        print(f"  Tem busca: {result['has_search']}")
        print(f"  Padrao download: {result['download_pattern']}")
        if result["game_links"]:
            print(f"  Jogos encontrados: {len(result['game_links'])}")
            for href, text in result["game_links"][:3]:
                print(f"    {text[:40]} -> {href[:60]}")
        if result["error"]:
            print(f"  Erro: {result['error']}")

        # Se tem jogos, testar download
        if result["has_psx"] and result["game_links"]:
            print(f"  Testando download...")
            dl_url, dl_detail = test_site_download(name, url, result["game_links"][0])
            if dl_url:
                print(f"  DOWNLOAD OK: {dl_url[:80]}")
                result["download_url"] = dl_url
                result["download_detail"] = dl_detail
            else:
                print(f"  Download falhou: {dl_detail}")

        results.append(result)
        time.sleep(1)

    # Salvar resultados
    results_path = STATE_DIR / "site_discovery.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResultados salvos: {results_path}")

    # Resumo
    accessible = [r for r in results if r["accessible"]]
    with_psx = [r for r in results if r["has_psx"]]
    with_serials = [r for r in results if r["has_serials"]]
    with_download = [r for r in results if r.get("download_url")]
    with_jp = [r for r in results if r["has_jp"]]

    print(f"\n{'='*60}")
    print(f"RESUMO:")
    print(f"  Sites testados: {len(results)}")
    print(f"  Acessiveis: {len(accessible)}")
    print(f"  Com PSX: {len(with_psx)}")
    print(f"  Com seriais: {len(with_serials)}")
    print(f"  Com JP: {len(with_jp)}")
    print(f"  Com download funcional: {len(with_download)}")
    print(f"{'='*60}")

    # Listar sites promissores
    if with_download:
        print(f"\nSites com download funcional:")
        for r in with_download:
            print(f"  {r['name']}: {r['download_url'][:80]}")

    return results


def implement_site(result):
    """Implementa um site detectado, adicionando ao sites.json."""
    if not result.get("download_url"):
        return False, "sem download funcional"

    name = result["name"]
    base_url = result["url"]

    # Carregar sites.json
    sites = {}
    if SITES_PATH.exists():
        sites = json.loads(SITES_PATH.read_text(encoding="utf-8"))

    # Verificar se ja existe
    if name in sites:
        return False, "ja existe no sites.json"

    # Detectar tipo de busca
    search_url = base_url
    if result["has_search"] and result["search_pattern"]:
        search_url = urljoin(base_url, result["search_pattern"])
        if "?" not in search_url:
            search_url += "?q={query}"

    # Adicionar site
    sites[name] = {
        "url": base_url,
        "search_url": search_url.replace("?q=", "?q={query}") if "?q=" not in search_url else search_url,
        "type": "direct_search",
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
        "auto_implemented": True,
        "has_jp": result["has_jp"],
        "has_eur": result["has_eur"],
        "has_serials": result["has_serials"],
        "download_pattern": result["download_pattern"],
    }

    SITES_PATH.write_text(json.dumps(sites, indent=2, ensure_ascii=False), encoding="utf-8")
    return True, f"adicionado: {name}"


def implement_discovered():
    """Implementa sites descobertos que tem download funcional."""
    results_path = STATE_DIR / "site_discovery.json"
    if not results_path.exists():
        print("Nenhum resultado de descoberta encontrado. Rode --discover primeiro.")
        return

    results = json.loads(results_path.read_text(encoding="utf-8"))
    implemented = 0
    for r in results:
        if r.get("download_url"):
            ok, msg = implement_site(r)
            print(f"  {r['name']}: {msg}")
            if ok:
                implemented += 1
    print(f"\nSites implementados: {implemented}")


if __name__ == "__main__":
    import sys
    if "--discover" in sys.argv:
        discover_sites()
    elif "--test" in sys.argv:
        # Testar sites ja conhecidos
        sites = json.loads(SITES_PATH.read_text(encoding="utf-8"))
        for name, cfg in sites.items():
            if cfg.get("enabled"):
                print(f"\n--- {name} ---")
                result = test_site_accessibility(name, cfg["url"])
                print(f"  Acessivel: {result['accessible']}")
                print(f"  Tem PSX: {result['has_psx']}")
                print(f"  Tem JP: {result['has_jp']}, EUR: {result['has_eur']}")
    elif "--implement" in sys.argv:
        implement_discovered()
    else:
        print("Uso: python auto_sites.py [--discover|--test|--implement]")
        print("  --discover: Descobrir e testar novos sites")
        print("  --test: Testar sites ja conhecidos")
        print("  --implement: Implementar sites descobertos com download funcional")
