#!/usr/bin/env python3
"""
discovery_agent.py — Agente contínuo de descoberta de novas fontes de ROMs PSX/PS1.

Objetivo: encontrar sites que hospedem ROMs/ISOs de PlayStation 1 e registrá-los
em discovery_candidates.json / discovery_searchable.json, sem modificar sites.json.

Roda em loop infinito, uma rodada a cada 60 minutos.
"""

import json
import logging
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ============================================================
# CONFIG
# ============================================================

STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
CANDIDATES_PATH = STATE_DIR / "discovery_candidates.json"
SEARCHABLE_PATH = STATE_DIR / "discovery_searchable.json"
SEED_PATH = STATE_DIR / "discovery_seed.json"
LOG_PATH = STATE_DIR / "discovery_agent.log"

STATE_DIR.mkdir(parents=True, exist_ok=True)


class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler que não quebra se stdout/stderr estiver inválido."""
    def emit(self, record):
        try:
            super().emit(record)
        except OSError:
            pass
    def flush(self):
        try:
            super().flush()
        except OSError:
            pass


log_handlers = [logging.FileHandler(LOG_PATH, encoding="utf-8")]
try:
    if sys.stdout is not None and sys.stdout.fileno() >= 0:
        log_handlers.append(SafeStreamHandler(sys.stdout))
except (OSError, ValueError):
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers,
)
log = logging.getLogger("discovery_agent")

SEARCH_TERMS = [
    "playstation roms download site",
    "psx roms download",
    "ps1 iso download",
    "SLUS-01449 psx rom download",
    "playstation 1 rom pack",
    "psx chd download",
    "ps1 bin cue download",
    "psx eboot download",
    "playstation 1 iso archive",
    "ps1 roms direct download",
]

IGNORED_DOMAINS = {
    "youtube.com", "youtu.be", "reddit.com", "wikipedia.org", "github.com",
    "google.com", "duckduckgo.com", "bing.com", "yahoo.com", "ask.com",
    "facebook.com", "twitter.com", "x.com", "instagram.com", "tiktok.com",
    "quora.com", "pinterest.com", "tumblr.com", "linkedin.com",
    "archive.org", "vimm.net", "coolrom.com", "romsfun.com", "romspedia.com",
    "retroiso.com", "retrostic.com", "romsdl.com", "romsgames.net", "romhustler.org",
    "retromania.gg", "cdromance.org", "hexrom.com", "consoleroms.com", "romulation.com",
    "psxdatacenter.com", "romsbase.com",
}

PSX_KEYWORDS = {
    "playstation", "psx", "ps1", "psone", "sony", "roms", "iso", "chd",
    "cue", "bin", "img", "ecm", "pbp", "download", "retroarch",
}

SEARCH_PATTERNS = [
    re.compile(r"[?&]s=", re.I),
    re.compile(r"/search[/?]", re.I),
    re.compile(r"search[?]", re.I),
    re.compile(r"q=", re.I),
    re.compile(r"query=", re.I),
]

MAX_WORKERS_VERIFY = 12
REQUEST_TIMEOUT = 20
SLEEP_BETWEEN_ROUNDS = 3600

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ============================================================
# UTILS
# ============================================================

def normalize_domain(url: str) -> str | None:
    try:
        parsed = urlparse(url if url.startswith("http") else f"http://{url}")
        netloc = parsed.netloc.lower().removeprefix("www.")
        if not netloc or "." not in netloc:
            return None
        return netloc
    except Exception:
        return None


def is_ignored_domain(domain: str) -> bool:
    domain = domain.lower().removeprefix("www.")
    for ignored in IGNORED_DOMAINS:
        if domain == ignored or domain.endswith(f".{ignored}"):
            return True
    return False


def atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        log.error(f"Erro ao salvar {path}: {e}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def load_json(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            log.warning(f"Falha ao carregar {path}: {e}")
    return default


# ============================================================
# BUSCADORES
# ============================================================

def _extract_urls_from_html(html: str) -> list[str]:
    urls = []
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("http"):
            urls.append(href)
        elif href.startswith("//"):
            urls.append(f"https:{href}")
    return urls


def search_with_playwright(url: str, term: str) -> list[str]:
    """Faz uma busca em uma URL usando Playwright e retorna URLs dos resultados."""
    urls = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=HEADERS["User-Agent"])
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Aguarda brevemente carregamento dinâmico
            time.sleep(3)
            urls = _extract_urls_from_html(page.content())
            browser.close()
    except Exception as e:
        log.warning(f"Playwright falhou para {url}: {e}")
    return urls


def search_duckduckgo(term: str) -> list[str]:
    query = urllib.parse.quote_plus(term)
    url = f"https://duckduckgo.com/html/?q={query}"
    urls = search_with_playwright(url, term)
    log.info(f"DuckDuckGo: {len(urls)} resultados para '{term}'")
    return urls


def search_bing(term: str) -> list[str]:
    query = urllib.parse.quote_plus(term)
    url = f"https://www.bing.com/search?q={query}"
    urls = search_with_playwright(url, term)
    log.info(f"Bing: {len(urls)} resultados para '{term}'")
    return urls


SEARXNG_INSTANCES = [
    "https://search.sapti.me",
    "https://search.bus-hit.me",
    "https://searx.tiekoetter.com",
    "https://searxng.nicfab.eu",
    "https://searx.be",
    "https://search.rhscz.eu",
    "https://searx.drgns.space",
    "https://search.ononoki.org",
]


def search_searxng(term: str, instance: str) -> list[str]:
    urls = []
    try:
        params = {"q": term, "format": "json", "language": "en-US"}
        resp = requests.get(
            f"{instance.rstrip('/')}/search",
            params=params,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        for result in data.get("results", []):
            url = result.get("url") or result.get("pretty_url")
            if url:
                urls.append(url)
        log.info(f"SearXNG ({instance}): {len(urls)} resultados para '{term}'")
    except Exception as e:
        log.debug(f"SearXNG ({instance}) falhou para '{term}': {e}")
    return urls


def search_searxng_any(term: str) -> list[str]:
    urls = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(search_searxng, term, inst): inst for inst in SEARXNG_INSTANCES}
        for future in as_completed(futures):
            try:
                urls.extend(future.result())
            except Exception as e:
                log.debug(f"Erro em SearXNG: {e}")
    return urls


def search_term(term: str) -> list[str]:
    """Tenta múltiplos buscadores e junta resultados."""
    urls = search_duckduckgo(term)
    if not urls:
        urls = search_bing(term)
    if not urls:
        urls = search_searxng_any(term)
    return urls


def extract_domains(urls: list[str]) -> set[str]:
    domains = set()
    for url in urls:
        domain = normalize_domain(url)
        if domain and not is_ignored_domain(domain):
            domains.add(domain)
    return domains


def load_seed_domains() -> set[str]:
    """Lê discovery_seed.json (URLs/domínios enviados pelo operador) e retorna domínios."""
    domains = set()
    if not SEED_PATH.exists():
        return domains
    try:
        data = load_json(SEED_PATH, {"urls": [], "domains": []})
        domains.update(extract_domains(data.get("urls", [])))
        for d in data.get("domains", []):
            nd = normalize_domain(d)
            if nd and not is_ignored_domain(nd):
                domains.add(nd)
        # Renomeia o seed para evitar reprocessamento
        processed = SEED_PATH.with_suffix(SEED_PATH.suffix + ".processed")
        try:
            if processed.exists():
                processed.unlink()
            SEED_PATH.rename(processed)
            log.info(f"Seed processado e movido para {processed}")
        except Exception as e:
            log.warning(f"Não foi possível renomear seed: {e}")
    except Exception as e:
        log.error(f"Erro ao processar seed: {e}")
    return domains


# ============================================================
# VERIFICADOR DE SITES
# ============================================================

def _fetch_site(url: str, verify: bool = True) -> requests.Response | None:
    """Faz requisição com headers e opção de verificação SSL."""
    headers = dict(HEADERS)
    headers["Referer"] = "https://www.google.com/"
    try:
        return requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True, verify=verify)
    except requests.exceptions.SSLError:
        if verify:
            return _fetch_site(url, verify=False)
        raise


def verify_site(domain: str) -> dict:
    result = {
        "domain": domain,
        "reachable": False,
        "psx_relevant": False,
        "has_search": False,
        "score": 0,
        "keywords_found": [],
        "search_hints": [],
        "title": "",
        "error": "",
    }
    try:
        url = f"https://{domain}/"
        resp = _fetch_site(url)
        if resp is None:
            result["error"] = "No response"
            return result

        result["reachable"] = resp.status_code == 200
        if not result["reachable"]:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        text = resp.text.lower()
        soup = BeautifulSoup(resp.text, "html.parser")
        title_tag = soup.find("title")
        result["title"] = title_tag.get_text(strip=True) if title_tag else ""

        found = [kw for kw in PSX_KEYWORDS if kw in text]
        result["keywords_found"] = found
        result["psx_relevant"] = len(found) >= 2 or (
            any(k in found for k in ("playstation", "psx", "ps1")) and "download" in found
        )

        for pat in SEARCH_PATTERNS:
            if pat.search(resp.text):
                result["has_search"] = True
                result["search_hints"].append(pat.pattern)
                break

        result["score"] = len(found) + (2 if result["has_search"] else 0)

    except requests.exceptions.SSLError as e:
        result["error"] = f"SSL error: {e}"
    except requests.exceptions.ConnectionError as e:
        # tenta http como fallback
        try:
            resp = requests.get(f"http://{domain}/", headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code == 200:
                result["reachable"] = True
                text = resp.text.lower()
                found = [kw for kw in PSX_KEYWORDS if kw in text]
                result["keywords_found"] = found
                result["psx_relevant"] = len(found) >= 2 or (
                    any(k in found for k in ("playstation", "psx", "ps1")) and "download" in found
                )
                for pat in SEARCH_PATTERNS:
                    if pat.search(resp.text):
                        result["has_search"] = True
                        result["search_hints"].append(pat.pattern)
                        break
                result["score"] = len(found) + (2 if result["has_search"] else 0)
                return result
        except Exception:
            pass
        result["error"] = f"Connection error: {e}"
    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
    except Exception as e:
        result["error"] = f"Exception: {e}"

    return result


def verify_sites(domains: set[str]) -> list[dict]:
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_VERIFY) as executor:
        future_to_domain = {executor.submit(verify_site, d): d for d in domains}
        for future in as_completed(future_to_domain):
            try:
                results.append(future.result())
            except Exception as e:
                log.error(f"Erro inesperado verificando {future_to_domain[future]}: {e}")
    return results


# ============================================================
# LOOP PRINCIPAL
# ============================================================

def run_round() -> None:
    log.info("=" * 60)
    log.info("Iniciando nova rodada de descoberta")

    candidates_state = load_json(CANDIDATES_PATH, {"last_update": None, "candidates": []})
    searchable_state = load_json(SEARCHABLE_PATH, {"last_update": None, "searchable": []})

    existing_candidates = set(candidates_state.get("candidates", []))
    existing_searchable = set(searchable_state.get("searchable", []))

    seed_domains = load_seed_domains()
    all_new_domains = set(seed_domains)

    if seed_domains:
        log.info(f"Seed com {len(seed_domains)} domínios; pulando buscadores para economizar tempo")
    else:
        all_urls = []
        for term in SEARCH_TERMS:
            log.info(f"Buscando: {term}")
            urls = search_term(term)
            all_urls.extend(urls)
            time.sleep(2)
        new_domains = extract_domains(all_urls)
        all_new_domains |= new_domains
        log.info(f"Domínios novos extraídos (busca): {len(new_domains)}")

    log.info(f"Domínios novos do seed: {len(seed_domains)}")

    domains_to_verify = all_new_domains - existing_candidates - existing_searchable
    if not domains_to_verify:
        log.info("Nenhum domínio novo para verificar nesta rodada")
    else:
        log.info(f"Verificando {len(domains_to_verify)} domínios...")
        results = verify_sites(domains_to_verify)

        promising = []
        searchable = []

        for r in results:
            domain = r["domain"]
            if not r["reachable"]:
                log.info(f"[INACESSÍVEL] {domain}: {r['error']}")
                continue

            if r["psx_relevant"]:
                promising.append(r)
                existing_candidates.add(domain)
                log.info(f"[PROMISSOR] {domain} score={r['score']} keywords={r['keywords_found']} search={r['has_search']}")

                if r["has_search"]:
                    searchable.append(r)
                    existing_searchable.add(domain)
            else:
                log.debug(f"[IRRELEVANTE] {domain}: poucas keywords ({r['keywords_found']})")

        if promising:
            promising.sort(key=lambda x: x["score"], reverse=True)
            candidates_state["candidates"] = [r["domain"] for r in promising] + [
                d for d in existing_candidates if d not in {r["domain"] for r in promising}
            ]

        if searchable:
            searchable.sort(key=lambda x: x["score"], reverse=True)
            searchable_state["searchable"] = [r["domain"] for r in searchable] + [
                d for d in existing_searchable if d not in {r["domain"] for r in searchable}
            ]

    now = datetime.now(timezone.utc).isoformat()
    candidates_state["last_update"] = now
    searchable_state["last_update"] = now

    atomic_write_json(CANDIDATES_PATH, candidates_state)
    atomic_write_json(SEARCHABLE_PATH, searchable_state)

    log.info(f"Candidatos registrados: {len(candidates_state['candidates'])}")
    log.info(f"Sites com busca registrados: {len(searchable_state['searchable'])}")
    log.info("Rodada concluída")


def main() -> None:
    log.info("Discovery agent iniciado (modo Playwright)")
    while True:
        try:
            run_round()
        except Exception as e:
            log.error(f"Erro na rodada: {e}", exc_info=True)
        log.info(f"Dormindo {SLEEP_BETWEEN_ROUNDS}s até a próxima rodada")
        time.sleep(SLEEP_BETWEEN_ROUNDS)


if __name__ == "__main__":
    main()
