"""Descoberta continua de novos sites de ROMs PSX.
Roda em loop infinito, buscando na web e testando candidatos.
Adiciona sites validos ao sites.json para o importre usar.
"""
import json
import re
import sys
import time
import logging
from pathlib import Path
from urllib.parse import quote_plus, urlparse

PSX_DIR = Path(__file__).parent.resolve()
STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
STATE_DIR.mkdir(parents=True, exist_ok=True)
SITES_PATH = STATE_DIR / "sites.json"
LEARNING_PATH = STATE_DIR / "learning.json"
LOG_PATH = STATE_DIR / "site_discovery.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("site_discovery")

sys.path.insert(0, str(PSX_DIR))
try:
    import requests
except Exception as e:
    log.error(f"requests nao disponivel: {e}")
    sys.exit(1)

KNOWN_SITES = {
    "archive.org", "vimm.net", "coolrom.com", "romsfun.com", "romspedia.com",
    "retroiso.com", "retrostic.com", "romsdl.com", "romsgames.net", "romhustler.org",
    "retromania.gg", "cdromance.org", "hexrom.com", "consoleroms.com", "romulation.com",
    "psxdatacenter.com", "romsbase.com", "google.com", "duckduckgo.com",
}
# Sites banidos permanentemente (nao reativar pelo discovery)
BANNED_SITES = {"romsfun.com", "romhustler.org", "romsbase.com", "emuparadise.me"}

SEARCH_QUERIES = [
    "playstation roms download site",
    "psx roms download",
    "ps1 roms download",
    "playstation 1 iso download",
    "SLUS-01449 psx rom download",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

CANDIDATES_PATH = STATE_DIR / "discovery_candidates.json"
SEARCHABLE_PATH = STATE_DIR / "discovery_searchable.json"


def load_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"load_json erro {path}: {e}")
        return default


def save_json(path, data):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    import os
    os.replace(tmp, str(path))


def discover_candidates_from_web():
    candidates = set()
    # 1) Ler candidatos descobertos pelo subagente de exploracao
    data = load_json(CANDIDATES_PATH, {})
    for domain in data.get("candidates", []):
        root = domain.lower().lstrip("www.")
        if root not in KNOWN_SITES:
            candidates.add(root)
    if candidates:
        log.info(f"Candidatos do subagente: {len(candidates)}")
    # 2) Fallback: busca propria via DuckDuckGo HTML (pode falhar por rate-limit)
    log.info("Iniciando busca na web por novos sites...")
    for query in SEARCH_QUERIES:
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                log.warning(f"DuckDuckGo retornou {resp.status_code} para query: {query}")
                continue
            for match in re.finditer(r'https?://[^"\'<>\s]+', resp.text):
                found_url = match.group(0)
                parsed = urlparse(found_url)
                domain = parsed.netloc.lower()
                if not domain or any(k in domain for k in ["duckduckgo", "google", "youtube", "wikipedia", "reddit"]):
                    continue
                root = domain.lstrip("www.")
                if root not in KNOWN_SITES:
                    candidates.add(root)
        except Exception as e:
            log.warning(f"Erro buscando '{query}': {e}")
    log.info(f"Total de candidatos: {len(candidates)}")
    return sorted(candidates)


def test_site(domain):
    test_urls = [f"https://{domain}/", f"https://www.{domain}/"]
    for test_url in test_urls:
        try:
            resp = requests.get(test_url, headers=HEADERS, timeout=15, allow_redirects=True)
            if resp.status_code >= 400:
                continue
            text = resp.text.lower()
            if any(k in text for k in ["playstation", "psx", "ps1", "roms", "iso", "download"]):
                has_search = any(h in text for h in ["/search", "?s=", "?search=", "/roms/", "/playstation"])
                return True, "direct_search" if has_search else "page_url"
            else:
                return False, "conteudo nao relacionado a ROMs"
        except Exception as e:
            log.debug(f"teste falhou para {test_url}: {e}")
            continue
    return False, "nao respondeu"


def add_site(domain, site_type):
    if domain in BANNED_SITES:
        log.info(f"Site {domain} banido — nao adicionado")
        return False
    sites = load_json(SITES_PATH, {})
    key = re.sub(r"[^a-z0-9_]+", "_", domain).strip("_")
    if key in sites:
        if domain in BANNED_SITES:
            log.info(f"Site {domain} banido — mantendo desativado")
            return False
        log.info(f"Site {domain} ja existe como '{key}'")
        return False
    sites[key] = {
        "url": f"https://{domain}",
        "search_url": f"https://{domain}/?s={{query}}",
        "type": site_type,
        "enabled": True,
        "fail_count": 0,
        "max_fails": 50,
        "discovered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    save_json(SITES_PATH, sites)
    log.info(f"NOVO SITE ADICIONADO: {domain} -> {key} ({site_type})")
    return True


def update_learning(domain, success=True):
    learning = load_json(LEARNING_PATH, {"site_stats": {}, "discovered_sites": []})
    learning.setdefault("site_stats", {})
    learning.setdefault("discovered_sites", [])
    key = re.sub(r"[^a-z0-9_]+", "_", domain).strip("_")
    stats = learning["site_stats"].setdefault(key, {"success": 0, "fail": 0, "attempts": 0})
    stats["attempts"] += 1
    if success:
        stats["success"] += 1
    else:
        stats["fail"] += 1
    if success and domain not in learning["discovered_sites"]:
        learning["discovered_sites"].append(domain)
    save_json(LEARNING_PATH, learning)


def main_loop():
    while True:
        try:
            log.info("=== Nova rodada de descoberta ===")
            candidates = discover_candidates_from_web()
            added = 0
            for domain in candidates:
                ok, hint = test_site(domain)
                update_learning(domain, success=ok)
                if ok:
                    if add_site(domain, hint):
                        added += 1
                else:
                    log.info(f"Descartado: {domain} ({hint})")
            log.info(f"Rodada finalizada: {added} novos sites adicionados")
        except Exception as e:
            log.error(f"Erro no main_loop: {e}")
        log.info("Aguardando 1h para proxima rodada...")
        time.sleep(3600)


if __name__ == "__main__":
    log.info("Site Discovery iniciado")
    main_loop()
