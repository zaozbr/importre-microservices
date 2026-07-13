r"""Subagente de descoberta continua de novas fontes de ROMs PS1.

Faz buscas na web periodicamente, extrai dominios promissores, verifica
conteudo e salva candidatos em:
  D:\roms\library\roms\_importre_state\discovery_candidates.json
  D:\roms\library\roms\_importre_state\discovery_searchable.json

Nao modifica sites.json — isso e feito por _site_discovery.py.
"""
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse

STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
STATE_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = STATE_DIR / "discovery_agent.log"
CANDIDATES_PATH = STATE_DIR / "discovery_candidates.json"
SEARCHABLE_PATH = STATE_DIR / "discovery_searchable.json"
WEB_RESULTS_PATH = STATE_DIR / "discovery_web_results.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8")],
)
log = logging.getLogger("web_discovery_subagent")

try:
    import requests
except Exception as e:
    log.error(f"requests nao disponivel: {e}")
    sys.exit(1)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
}

IGNORED_PREFIXES = ("www.", "m.", "mobile.")

IGNORED_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "reddit.com",
    "redd.it",
    "wikipedia.org",
    "github.com",
    "google.com",
    "duckduckgo.com",
    "bing.com",
    "playstation.com",
    "microsoft.com",
    "support.microsoft.com",
    "go.microsoft.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "ebay.com",
    "amazon.com",
    "bestbuy.com",
    "yahoo.com",
    "sonyinteractive.com",
    "thefreedictionary.com",
    "merriam-webster.com",
    "restaurantji.com",
    "powershelltips.com",
    "momaps1.org",
}

KNOWN_SITES = {
    "archive.org",
    "vimm.net",
    "coolrom.com",
    "romsfun.com",
    "romspedia.com",
    "retroiso.com",
    "retrostic.com",
    "romsdl.com",
    "romsgames.net",
    "romhustler.org",
    "retromania.gg",
    "cdromance.org",
    "hexrom.com",
    "consoleroms.com",
    "romulation.com",
    "psxdatacenter.com",
    "romsbase.com",
    "myrient.erista.me",
    "emuparadise.me",
    "romspack.com",
    "freeroms.com",
    "wowroms.com",
    "totalroms.com",
    "retro-bit.ru",
    "roms2000.com",
    "classicgames.me",
    "romspure.cc",
    "emulatorgames.net",
    "gamulator.com",
    "psx2pspeboots.blogspot.com",
    "retroemulators.com",
    "allmyroms.net",
    "techtoroms.com",
    "syam.eu.org",
    "hauber.cc",
}

SEARCH_QUERIES = [
    '"psx roms" download',
    '"ps1 roms" download',
    '"playstation roms" download',
    '"ps1 iso" download',
    '"psx iso" download',
    '"psx chd" download',
    "SLUS-01449 download",
    "SLES-00001 psx rom",
    "SCUS-00001 psx rom",
    "retro roms psx",
    "play retrogames psx",
    "psx rom pack",
    "playstation 1 rom set",
    "psx redump chd",
]

PSX_KEYWORDS = ["playstation", "psx", "ps1", "roms", "iso", "download"]
SEARCH_HINTS = ["/search", "?s=", "?search=", "/roms/", "/playstation", "/psx", "/ps1"]


def load_json(path, default):
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


def normalize_domain(domain):
    domain = domain.lower().strip()
    for prefix in IGNORED_PREFIXES:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain


def is_ignored(domain):
    root = normalize_domain(domain)
    if root in IGNORED_DOMAINS or root in KNOWN_SITES:
        return True
    if not "." in root:
        return True
    # bloqueia subdominios de dominios ignorados/conhecidos
    parts = root.split(".")
    for i in range(len(parts) - 1):
        parent = ".".join(parts[i:])
        if parent in IGNORED_DOMAINS or parent in KNOWN_SITES:
            return True
    return False


def fetch_duckduckgo(query):
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        if resp.status_code != 200:
            log.warning(f"DuckDuckGo retornou {resp.status_code} para: {query}")
            return ""
        return resp.text
    except Exception as e:
        log.warning(f"Erro DuckDuckGo '{query}': {e}")
        return ""


_BING_SESSION = None


def get_bing_session():
    global _BING_SESSION
    if _BING_SESSION is None:
        _BING_SESSION = requests.Session()
        _BING_SESSION.headers.update(HEADERS)
        # visita a home do Bing para obter cookies de sessao
        try:
            _BING_SESSION.get("https://www.bing.com/", timeout=15)
        except Exception:
            pass
    return _BING_SESSION


def fetch_bing(query):
    url = f"https://www.bing.com/search?q={quote_plus(query)}&setmkt=en-US&setlang=en&form=QBLH"
    try:
        session = get_bing_session()
        resp = session.get(url, timeout=25)
        if resp.status_code != 200:
            log.warning(f"Bing retornou {resp.status_code} para: {query}")
            return ""
        return resp.text
    except Exception as e:
        log.warning(f"Erro Bing '{query}': {e}")
        return ""


def fetch_search(query):
    """Tenta Bing primeiro; em caso de falha/resultado vazio, cai no DuckDuckGo.
    Retorna (html, source)."""
    html = fetch_bing(query)
    if html:
        return html, "bing"
    log.info(f"  Bing vazio/falhou, tentando DuckDuckGo para: {query}")
    return fetch_duckduckgo(query), "ddg"


def _decode_bing_u(raw_u):
    """Decodifica o parametro 'u' dos redirecionamentos /ck/a do Bing."""
    import base64

    if not raw_u:
        return None
    # remove prefixos conhecidos (a1, a3L, etc.)
    s = raw_u.strip()
    for prefix in ("a1", "a3L"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    # Bing usa base64url; converte para padrao para b64decode
    s = s.replace("_", "/").replace("-", "+")
    padded = s + "=" * ((4 - len(s) % 4) % 4)
    try:
        decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:
        return None
    # pode ser URL absoluta ou path relativo do Bing
    if decoded.startswith("http://") or decoded.startswith("https://"):
        return decoded
    if decoded.startswith("/"):
        return f"https://www.bing.com{decoded}"
    return None


def extract_bing_domains(html):
    domains = set()
    if not html:
        return domains
    # links de redirecionamento criptografados do Bing
    links = re.findall(r'href="(https://www\.bing\.com/ck/a[^"]+)"', html)
    log.debug(f"extract_bing_domains: {len(links)} raw ck links")
    for link in links:
        # converte entidades HTML (&amp; -> &) para parsear parametros
        link = link.replace("&amp;", "&")
        # extrai parametro u
        m = re.search(r'[?&]u=([^&"]+)', link)
        if not m:
            continue
        raw_u = m.group(1)
        try:
            from urllib.parse import unquote

            raw_u = unquote(raw_u)
        except Exception:
            pass
        final_url = _decode_bing_u(raw_u)
        if not final_url:
            continue
        parsed = urlparse(final_url)
        domain = normalize_domain(parsed.netloc)
        log.debug(f"  decoded: {final_url} -> {domain} (ignored={is_ignored(domain)})")
        if not domain or is_ignored(domain):
            continue
        domains.add(domain)
    return domains


def extract_ddg_domains(html):
    domains = set()
    if not html:
        return domains
    patterns = [
        r'uddg=([^"\'<>\s]+)',
        r'href="(https?://[^"]+)"',
        r'https?://[^"\'<>\s]+',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html):
            url = match.group(1) if match.lastindex else match.group(0)
            if not url:
                continue
            try:
                parsed = urlparse(url)
                domain = normalize_domain(parsed.netloc)
                if not domain or is_ignored(domain):
                    continue
                domains.add(domain)
            except Exception:
                continue
    return domains


def extract_domains(html, source="bing"):
    if source == "bing":
        return extract_bing_domains(html)
    return extract_ddg_domains(html)


def verify_site(domain):
    """Tenta acessar https://domain/ e verifica keywords de PSX/busca."""
    urls = [f"https://{domain}/", f"https://www.{domain}/"]
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
            if resp.status_code >= 400:
                continue
            text = resp.text.lower()
            if any(k in text for k in PSX_KEYWORDS):
                has_search = any(h in text for h in SEARCH_HINTS)
                return True, has_search
            else:
                return False, "conteudo nao relacionado"
        except Exception as e:
            log.debug(f"verify {url} falhou: {e}")
            continue
    return False, "nao respondeu"


def run_discovery_round():
    log.info("=== Iniciando rodada de descoberta web ===")

    candidates_data = load_json(CANDIDATES_PATH, {"last_update": None, "candidates": []})
    searchable_data = load_json(SEARCHABLE_PATH, {"last_update": None, "searchable": []})

    existing_candidates = set(candidates_data.get("candidates", []))
    existing_searchable = set(searchable_data.get("searchable", []))

    new_candidates = set()
    new_searchable = set()

    # domínios enviados pelo agente via web_search
    web_results = load_json(WEB_RESULTS_PATH, {"domains": []})
    agent_domains = set(web_results.get("domains", []))
    log.info(f"Domínios do agente web_search: {len(agent_domains)}")

    all_source_domains = set()

    for idx, query in enumerate(SEARCH_QUERIES):
        log.info(f"Buscando: {query}")
        html, source = fetch_search(query)
        domains = extract_domains(html, source=source)
        log.info(f"  {len(domains)} dominios extraidos ({source})")
        all_source_domains.update(domains)
        # pequeno delay para nao ser rate-limitado
        if idx < len(SEARCH_QUERIES) - 1:
            time.sleep(2)

    # combina domínios do Bing/DuckDuckGo com os enviados pelo agente
    combined_domains = all_source_domains | agent_domains
    log.info(f"Total de dominios unicos para verificar: {len(combined_domains)}")

    for domain in combined_domains:
        if domain in existing_candidates or domain in new_candidates:
            continue
        log.info(f"Verificando: {domain}")
        ok, has_search = verify_site(domain)
        if ok:
            log.info(f"  PROMISSOR: {domain}")
            new_candidates.add(domain)
            if has_search:
                log.info(f"  BUSCAVEL: {domain}")
                new_searchable.add(domain)
        else:
            log.info(f"  descartado: {domain} ({has_search})")

    now = datetime.now(timezone.utc).isoformat()

    updated_candidates = sorted(existing_candidates | new_candidates)
    candidates_data["last_update"] = now
    candidates_data["candidates"] = updated_candidates
    save_json(CANDIDATES_PATH, candidates_data)

    updated_searchable = sorted(existing_searchable | new_searchable)
    searchable_data["last_update"] = now
    searchable_data["searchable"] = updated_searchable
    save_json(SEARCHABLE_PATH, searchable_data)

    log.info(
        f"Rodada finalizada: {len(new_candidates)} novos candidatos, "
        f"{len(new_searchable)} novos buscaveis"
    )


def main():
    log.info("Web Discovery Subagent iniciado")
    while True:
        try:
            run_discovery_round()
        except Exception as e:
            log.exception(f"Erro na rodada: {e}")
        log.info("Dormindo 3600s ate a proxima rodada...")
        time.sleep(3600)


if __name__ == "__main__":
    main()
