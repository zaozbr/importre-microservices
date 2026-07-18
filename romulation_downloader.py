#!/usr/bin/env python3
"""
PSX ROM Downloader + CHD Converter
Baixa jogos PSX faltantes do archive.org (primario) e Romulation (fallback).
Converte para CHD com chdman.

Estrategia de busca no archive.org:
1. serialnumber:SERIAL (campo de metadados)
2. "SERIAL" (busca textual)
3. Titulo + collection:psxgames
4. Titulo + "playstation" (busca ampla)
"""
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote, quote_plus

import requests
from bs4 import BeautifulSoup

# === CONFIG ===
LISTA_FILE = r"F:\importre_state\lista_ainda_faltam.txt"
CHD_DIR = r"D:\roms\library\roms\psx"
DL_DIR = r"F:\downloads\psx_faltantes"
CHDMAN = r"F:\importre\chdman.exe"
SEVENZR = r"F:\importre\7zr.exe"
ARIA2C = r"F:\importre\aria2c.exe"
PROGRESS_FILE = r"F:\importre_state\download_progress.json"
LOG_FILE = r"F:\importre_state\romulation_downloader.log"
LOCK_FILE = r"F:\importre_state\romulation_downloader.lock"

BASE_URL = "https://www.romulation.org"
SEARCH_URL = "https://www.romulation.org/roms/PSX?filter={}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

REGION_ORDER = {"USA": 0, "PAL": 1, "JPN": 2, "HBREW": 3}
REGION_KEYWORDS = {
    "USA": ["(USA)", "(U)"],
    "PAL": ["(Europe)", "(E)", "(Germany)", "(France)", "(Italy)", "(Spain)", "(UK)"],
    "JPN": ["(Japan)", "(J)"],
}
DEMO_KEYWORDS = ["demo", "trial", "sample", "taikenban", "net yaroze", "jampack", "sled-"]

MAX_RETRIES = 3
DOWNLOAD_TIMEOUT = 600
GUEST_COOLDOWN = 10
ROMULATION_503_BACKOFF = 300  # 5 min backoff after 503

# Archive.org rate limiting: be polite
ARCHIVE_DELAY = 2  # seconds between archive.org API calls
ARIA2_CONNECTIONS = 16  # multi-connection downloads via aria2c


# === LOGGING ===
def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    # Safe print (handle non-ASCII characters on Windows console)
    try:
        print(line, flush=True)
    except Exception:
        try:
            safe = line.encode("ascii", "replace").decode("ascii")
            print(safe, flush=True)
        except Exception:
            pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# === SINGLE INSTANCE LOCK ===
def acquire_lock():
    """Prevent multiple instances from running simultaneously."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            # Check if process is still running
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                PROCESS_QUERY_INFORMATION = 0x0400
                handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    log(f"ERRO: Outra instancia ja esta rodando (PID {pid}). Saindo.")
                    sys.exit(1)
            except Exception:
                pass
        except Exception:
            pass
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


# === HELPERS ===
def sanitize_name(name):
    nf = unicodedata.normalize("NFKD", name)
    ascii_str = nf.encode("ascii", "ignore").decode("ascii")
    ascii_str = re.sub(r"[^\w\s-]", "", ascii_str)
    ascii_str = re.sub(r"\s+", "-", ascii_str.strip())
    ascii_str = re.sub(r"-+", "-", ascii_str)
    return ascii_str


def is_demo(title):
    low = title.lower()
    return any(kw in low for kw in DEMO_KEYWORDS)


def parse_list_line(line):
    line = line.strip()
    if not line:
        return None
    m = re.match(r"^\d+\.\s*(.+)$", line)
    if not m:
        return None
    rest = m.group(1)
    rm = re.search(r"\[(\w+)\]\s*$", rest)
    region = rm.group(1) if rm else "UNK"
    rest = rest[: rm.start()].strip() if rm else rest
    sm = re.match(r"^([A-Z]+-[A-Z0-9]+)\s*-\s*(.+)$", rest)
    if not sm:
        return None
    serial = sm.group(1)
    title = sm.group(2).strip()
    return {"serial": serial, "title": title, "region": region, "raw": line}


def load_list():
    games = []
    with open(LISTA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            g = parse_list_line(line)
            if g and not is_demo(g["title"]) and not is_demo(g["serial"]):
                games.append(g)
    games.sort(key=lambda g: (REGION_ORDER.get(g["region"], 99), g["serial"]))
    return games


def load_progress():
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"completed": {}, "failed": {}, "skipped": {}, "last_index": 0}


def save_progress(progress):
    try:
        tmp = PROGRESS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
        os.replace(tmp, PROGRESS_FILE)
    except Exception as e:
        log(f"ERRO ao salvar progresso: {e}")


def chd_exists(serial):
    try:
        for f in os.listdir(CHD_DIR):
            if f.lower().endswith(".chd") and serial.lower() in f.lower():
                return os.path.join(CHD_DIR, f)
    except Exception:
        pass
    return None


def title_match_score(search_title, item_title):
    """Score how well two titles match (0-100)."""
    s_words = set(re.findall(r"\w+", search_title.lower()))
    i_words = set(re.findall(r"\w+", item_title.lower()))
    s_words.discard("the")
    s_words.discard("of")
    i_words.discard("the")
    i_words.discard("of")
    if not s_words:
        return 0
    matching = s_words & i_words
    return len(matching) / len(s_words) * 100


# === ARCHIVE.ORG (PRIMARY) ===
def archive_search(serial, title):
    """
    Multi-strategy search for a PSX ROM on archive.org.
    Returns list of (identifier, item_title, serialnumber) tuples.
    """
    results = []
    seen_ids = set()

    def add_results(docs):
        for doc in docs:
            ident = doc.get("identifier", "")
            if ident and ident not in seen_ids:
                seen_ids.add(ident)
                t = doc.get("title", "")
                sn = doc.get("serialnumber", "")
                results.append((ident, t, sn))

    # Strategy 1: serialnumber field
    query1 = f"serialnumber:{quote(serial)}"
    url1 = f"https://archive.org/advancedsearch.php?q={query1}&fl[]=identifier&fl[]=title&fl[]=serialnumber&rows=20&output=json"
    try:
        resp = requests.get(url1, timeout=30, headers={"User-Agent": HEADERS["User-Agent"]})
        if resp.status_code == 200:
            docs = resp.json().get("response", {}).get("docs", [])
            add_results(docs)
    except Exception as e:
        log(f"  [Archive] Erro busca serialnumber: {e}")
    time.sleep(ARCHIVE_DELAY)

    # Strategy 2: text search for serial in quotes
    if not results:
        query2 = quote(f'"{serial}"')
        url2 = f"https://archive.org/advancedsearch.php?q={query2}&fl[]=identifier&fl[]=title&fl[]=serialnumber&rows=20&output=json"
        try:
            resp = requests.get(url2, timeout=30, headers={"User-Agent": HEADERS["User-Agent"]})
            if resp.status_code == 200:
                docs = resp.json().get("response", {}).get("docs", [])
                add_results(docs)
        except Exception:
            pass
        time.sleep(ARCHIVE_DELAY)

    # Strategy 3: title keywords + psxgames collection
    if not results:
        clean_title = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
        words = [w for w in clean_title.split() if len(w) > 1]
        if len(words) >= 2:
            query3 = f'({" ".join(words[:3])}) AND collection:psxgames'
            url3 = f"https://archive.org/advancedsearch.php?q={quote(query3)}&fl[]=identifier&fl[]=title&fl[]=serialnumber&rows=20&output=json"
            try:
                resp = requests.get(url3, timeout=30, headers={"User-Agent": HEADERS["User-Agent"]})
                if resp.status_code == 200:
                    docs = resp.json().get("response", {}).get("docs", [])
                    # Filter by title match
                    filtered = []
                    for doc in docs:
                        item_title = doc.get("title", "")
                        score = title_match_score(clean_title, item_title)
                        if score >= 30:
                            filtered.append(doc)
                    add_results(filtered)
            except Exception:
                pass
        time.sleep(ARCHIVE_DELAY)

    # Strategy 4: first word + psxgames (broader)
    if not results:
        clean_title = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
        words = [w for w in clean_title.split() if len(w) > 1]
        if words:
            query4 = f'({words[0]}) AND collection:psxgames'
            url4 = f"https://archive.org/advancedsearch.php?q={quote(query4)}&fl[]=identifier&fl[]=title&fl[]=serialnumber&rows=30&output=json"
            try:
                resp = requests.get(url4, timeout=30, headers={"User-Agent": HEADERS["User-Agent"]})
                if resp.status_code == 200:
                    docs = resp.json().get("response", {}).get("docs", [])
                    # Filter by title match (lower threshold)
                    filtered = []
                    for doc in docs:
                        item_title = doc.get("title", "")
                        score = title_match_score(clean_title, item_title)
                        if score >= 50:
                            filtered.append(doc)
                    add_results(filtered)
            except Exception:
                pass
        time.sleep(ARCHIVE_DELAY)

    return results


def get_archive_files(identifier):
    """Get file list from an archive.org item. Returns (files_list, server)."""
    url = f"https://archive.org/metadata/{identifier}"
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": HEADERS["User-Agent"]})
        if resp.status_code != 200:
            return [], ""
        data = resp.json()
        files = data.get("files", [])
        result = []
        for f in files:
            name = f.get("name", "")
            fmt = f.get("format", "")
            size = f.get("size", "0")
            if any(name.lower().endswith(ext) for ext in [".7z", ".zip", ".rar", ".cue", ".bin", ".iso", ".chd"]):
                result.append({
                    "name": name,
                    "format": fmt,
                    "size": int(size) if str(size).isdigit() else 0,
                })
        return result, data.get("server", "")
    except Exception as e:
        log(f"  [Archive] Erro ao obter arquivos: {e}")
        return [], ""


def get_archive_metadata(identifier):
    """Get full metadata for an archive.org item (including serialnumber)."""
    url = f"https://archive.org/metadata/{identifier}"
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": HEADERS["User-Agent"]})
        if resp.status_code != 200:
            return {}
        data = resp.json()
        return data.get("metadata", {})
    except Exception:
        return {}


def aria2_download(url, dest_path, timeout=600):
    """
    Download a file using aria2c with multi-connection support.
    Returns True on success, False on failure.
    """
    if os.path.exists(dest_path):
        os.remove(dest_path)

    # Remove .aria2 control file if exists
    aria2_ctrl = dest_path + ".aria2"
    if os.path.exists(aria2_ctrl):
        os.remove(aria2_ctrl)

    cmd = [
        ARIA2C,
        "--max-tries=3",
        "--retry-wait=5",
        "--timeout=60",
        "--connect-timeout=30",
        f"--max-connection-per-server={ARIA2_CONNECTIONS}",
        f"--split={ARIA2_CONNECTIONS}",
        "--min-split-size=1M",
        "--console-log-level=error",
        "--summary-interval=0",
        "--file-allocation=none",
        f"--dir={os.path.dirname(dest_path)}",
        f"--out={os.path.basename(dest_path)}",
        f"--user-agent={HEADERS['User-Agent']}",
        "--check-certificate=true",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        url,
    ]

    try:
        # Use CREATE_NO_WINDOW to hide console, capture output as bytes to avoid encoding issues
        result = subprocess.run(cmd, capture_output=True, timeout=timeout,
                               creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        if result.returncode == 0 and os.path.exists(dest_path):
            size = os.path.getsize(dest_path)
            if size > 1024:
                return True
            else:
                log(f"  aria2: arquivo muito pequeno ({size} bytes)")
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                return False
        else:
            stderr = result.stderr.decode("utf-8", errors="replace")[:300] if result.stderr else ""
            log(f"  aria2 falhou (rc={result.returncode}): {stderr}")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False
    except subprocess.TimeoutExpired:
        log(f"  aria2 timeout ({timeout}s)")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False
    except Exception as e:
        log(f"  aria2 erro: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


def verify_serial(identifier, serial):
    """Check if an archive.org item has the correct serial number."""
    meta = get_archive_metadata(identifier)
    item_serial = meta.get("serialnumber", "")
    if item_serial:
        # Normalize: remove extra info like "(VX044-J1)"
        item_serial_clean = re.match(r"[A-Z]+-[A-Z0-9]+", item_serial.upper())
        if item_serial_clean:
            return item_serial_clean.group(0) == serial.upper()
        return item_serial.upper() == serial.upper()
    return None  # Unknown - no serialnumber field


def download_from_archive_org(serial, title, region):
    """
    Download from archive.org. Returns (path, is_chd) tuple or (None, False).
    """
    log(f"  [Archive] Buscando: {serial}")
    results = archive_search(serial, title)

    if not results:
        log(f"  [Archive] Nenhum resultado")
        return None, False

    # Try each result - verify serial when possible
    for identifier, item_title, item_serial in results:
        log(f"  [Archive] Item: {identifier} ({item_title[:40]})")

        # If item has serialnumber, verify it matches
        if item_serial:
            item_serial_clean = re.match(r"[A-Z]+-[A-Z0-9]+", item_serial.upper())
            if item_serial_clean and item_serial_clean.group(0) != serial.upper():
                log(f"  [Archive] Serial mismatch: {item_serial} != {serial}, pulando")
                continue
        else:
            # No serialnumber in search results - check metadata
            verified = verify_serial(identifier, serial)
            if verified is False:
                log(f"  [Archive] Serial mismatch (metadata), pulando")
                continue
            # If verified is None, we can't confirm - check title match
            if verified is None:
                clean_title = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
                score = title_match_score(clean_title, item_title)
                if score < 30:
                    log(f"  [Archive] Title mismatch ({score:.0f}%), pulando")
                    continue

        time.sleep(ARCHIVE_DELAY)
        files, server = get_archive_files(identifier)
        if not files:
            log(f"  [Archive] Sem arquivos baixaveis")
            continue

        # Priority 1: CHD file (already converted, just download)
        chd_file = None
        for f in files:
            if f["name"].lower().endswith(".chd") and f["size"] > 1024 * 1024:
                chd_file = f
                break

        if chd_file:
            filename = chd_file["name"]
            log(f"  [Archive] Baixando CHD: {filename} ({chd_file['size']/1024/1024:.1f} MB)")
            dl_url = f"https://archive.org/download/{identifier}/{quote(filename)}"

            safe_title = sanitize_name(title)
            chd_name = f"{safe_title}-{serial}.chd"
            dest = os.path.join(CHD_DIR, chd_name)

            t0 = time.time()
            ok = aria2_download(dl_url, dest, timeout=DOWNLOAD_TIMEOUT)
            dt = time.time() - t0
            if ok:
                size = os.path.getsize(dest)
                if size < 1024 * 1024:
                    if os.path.exists(dest):
                        os.remove(dest)
                    log(f"  [Archive] CHD muito pequeno")
                    return None, False
                speed = size / 1024 / 1024 / max(dt, 1)
                log(f"  [Archive] CHD OK: {size/1024/1024:.1f} MB in {dt:.1f}s ({speed:.1f} MB/s)")
                return dest, True  # is_chd=True, no conversion needed
            else:
                log(f"  [Archive] Falha no download CHD")
                if os.path.exists(dest):
                    os.remove(dest)
                return None, False

        # Priority 2: Archive file (7z, zip, rar)
        archive_file = None
        for f in files:
            if f["name"].lower().endswith((".7z", ".zip", ".rar")):
                archive_file = f
                break

        if not archive_file:
            # Priority 3: cue/bin/iso
            for f in files:
                if f["name"].lower().endswith((".cue", ".iso")):
                    archive_file = f
                    break

        if not archive_file:
            log(f"  [Archive] Nenhum arquivo baixavel")
            continue

        filename = archive_file["name"]
        log(f"  [Archive] Baixando: {filename}")

        dl_url = f"https://archive.org/download/{identifier}/{quote(filename)}"

        ext = os.path.splitext(filename)[1]
        dest = os.path.join(DL_DIR, f"{serial}_archive{ext}")

        t0 = time.time()
        ok = aria2_download(dl_url, dest, timeout=DOWNLOAD_TIMEOUT)
        dt = time.time() - t0
        if ok:
            size = os.path.getsize(dest)
            if size < 1024:
                if os.path.exists(dest):
                    os.remove(dest)
                log(f"  [Archive] Arquivo muito pequeno")
                continue
            speed = size / 1024 / 1024 / max(dt, 1)
            log(f"  [Archive] OK: {size/1024/1024:.1f} MB in {dt:.1f}s ({speed:.1f} MB/s)")
            return dest, False
        else:
            log(f"  [Archive] Falha no download")
            if os.path.exists(dest):
                os.remove(dest)
            continue

    log(f"  [Archive] Nenhum item valido encontrado")
    return None, False


# === ROMULATION (FALLBACK) ===
romulation_503_count = 0
romulation_503_until = 0  # timestamp until which we skip romulation


def search_romulation(session, title, serial):
    clean_title = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
    words = [w for w in clean_title.split() if len(w) > 1]
    search_terms = []
    if len(words) >= 2:
        search_terms.append(" ".join(words[:3]))
    search_terms.append(" ".join(words[:2]))
    if words:
        search_terms.append(words[0])

    seen = set()
    results = []
    for term in search_terms:
        url = SEARCH_URL.format(quote_plus(term))
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.select_one(".roms-table")
            if not table:
                continue
            for tr in table.find_all("tr"):
                a = tr.find("a", href=True)
                if a and "/rom/PSX/" in a["href"]:
                    href = a["href"]
                    full_url = href if href.startswith("http") else BASE_URL + href
                    rom_title = a.get_text(strip=True)
                    if full_url not in seen:
                        seen.add(full_url)
                        results.append((full_url, rom_title))
        except Exception as e:
            log(f"  Erro na busca '{term}': {e}")
        if results:
            break
    return results


def match_rom(serial, title, region, results):
    serial_low = serial.lower()
    title_low = title.lower()
    title_words = set(re.findall(r"\w+", title_low))
    title_words.discard("the")
    title_words.discard("of")

    best = None
    best_score = 0
    for rom_url, rom_title in results:
        rom_low = rom_title.lower()
        url_serial = re.search(r"[SUJ][CL][A-Z]-\d+", rom_url, re.I)
        if url_serial and url_serial.group(0).upper() != serial.upper():
            continue
        score = 0
        if serial_low in rom_low or serial_low.replace("-", "") in rom_low.replace("-", ""):
            score += 100
        rom_words = set(re.findall(r"\w+", rom_low))
        if title_words:
            matching = title_words & rom_words
            score += len(matching) / len(title_words) * 50
        if score > best_score:
            best_score = score
            best = (rom_url, rom_title)
    if best_score >= 25:
        return best
    return None


def get_download_links(session, rom_url):
    try:
        resp = session.get(rom_url, timeout=30)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        dl_link = None
        for a in soup.find_all("a", href=True):
            if "newdownload" in a["href"]:
                dl_link = a["href"]
                if not dl_link.startswith("http"):
                    dl_link = BASE_URL + dl_link
                break
        if not dl_link:
            return []
        resp2 = session.get(dl_link, timeout=30)
        if resp2.status_code != 200:
            return []
        soup2 = BeautifulSoup(resp2.text, "html.parser")
        body = soup2.find("body") or soup2
        links = []
        for a in body.find_all("a", href=True):
            if "pluto.romulation.net" in a["href"]:
                filename = a.get_text(strip=True)
                links.append((a["href"], filename))
        return links
    except Exception as e:
        log(f"  Erro ao obter links: {e}")
        return []


def select_best_link(region, links):
    if not links:
        return None
    keywords = REGION_KEYWORDS.get(region, [])
    for kw in keywords:
        for pluto_url, filename in links:
            if kw.lower() in filename.lower():
                return (pluto_url, filename)
    for pluto_url, filename in links:
        if "[!]" in filename:
            return (pluto_url, filename)
    return links[0]


def download_file(session, url, dest_path, referer=None):
    try:
        headers = {}
        if referer:
            headers["Referer"] = referer
        resp = session.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT, headers=headers)
        if resp.status_code != 200:
            text = resp.text[:200] if "text/html" in resp.headers.get("content-type", "") else ""
            if "concurrent connection" in text:
                return "rate_limited"
            log(f"  Download HTTP {resp.status_code}: {text[:100]}")
            return False
        ct = resp.headers.get("content-type", "")
        if "text/html" in ct:
            text = resp.text[:200]
            if "concurrent connection" in text:
                return "rate_limited"
            log(f"  Recebido HTML: {text[:100]}")
            return False
        total = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=256 * 1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
        if total < 1024:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False
        return True
    except Exception as e:
        log(f"  Erro no download: {e}")
        return False


def download_from_romulation(session, serial, title, region):
    global romulation_503_count, romulation_503_until

    # Check if we're in 503 backoff
    if time.time() < romulation_503_until:
        log(f"  Romulation em backoff 503 (restam {int(romulation_503_until - time.time())}s)")
        return None

    log(f"  [Romulation] Buscando: {serial} - {title[:40]}")
    results = search_romulation(session, title, serial)
    if not results:
        log(f"  [Romulation] Nenhum resultado")
        return None

    match = match_rom(serial, title, region, results)
    if not match:
        log(f"  [Romulation] Nenhum match")
        return None

    rom_url, rom_title = match
    log(f"  [Romulation] Match: {rom_title[:50]}")

    for attempt in range(MAX_RETRIES):
        if attempt > 0:
            time.sleep(GUEST_COOLDOWN)

        links = get_download_links(session, rom_url)
        if not links:
            continue

        selected = select_best_link(region, links)
        if not selected:
            continue

        pluto_url, filename = selected
        log(f"  [Romulation] Baixando: {filename}")

        ext = ".7z"
        if filename.lower().endswith(".rar"):
            ext = ".rar"
        elif filename.lower().endswith(".zip"):
            ext = ".zip"
        dest = os.path.join(DL_DIR, f"{serial}{ext}")
        if os.path.exists(dest):
            os.remove(dest)

        result = download_file(session, pluto_url, dest, referer=rom_url)
        if result is True:
            size = os.path.getsize(dest)
            log(f"  [Romulation] OK: {size/1024/1024:.1f} MB")
            return dest
        elif result == "rate_limited":
            romulation_503_count += 1
            log(f"  [Romulation] 503 rate limited (#{romulation_503_count})")
            if os.path.exists(dest):
                os.remove(dest)
            # Set backoff
            romulation_503_until = time.time() + ROMULATION_503_BACKOFF
            return None
        else:
            if os.path.exists(dest):
                os.remove(dest)
    return None


# === EXTRACTION + CHD ===
def extract_archive(archive_path, extract_dir):
    os.makedirs(extract_dir, exist_ok=True)
    try:
        result = subprocess.run(
            [SEVENZR, "x", archive_path, f"-o{extract_dir}", "-y"],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            files = []
            for root, dirs, fs in os.walk(extract_dir):
                for fn in fs:
                    files.append(os.path.join(root, fn))
            if files:
                return files
        else:
            log(f"  7zr stderr: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        log(f"  7zr timeout")
    except Exception as e:
        log(f"  7zr falhou: {e}")
    return []


def find_disc_files(extracted_files):
    cue_files = []
    iso_files = []
    bin_files = []
    for f in extracted_files:
        ext = os.path.splitext(f)[1].lower()
        if ext == ".cue":
            cue_files.append(f)
        elif ext == ".iso":
            iso_files.append(f)
        elif ext == ".bin":
            bin_files.append(f)

    if cue_files:
        cue = cue_files[0]
        cue_base = os.path.splitext(os.path.basename(cue))[0]
        matching_bin = None
        for b in bin_files:
            if os.path.splitext(os.path.basename(b))[0] == cue_base:
                matching_bin = b
                break
        if not matching_bin and bin_files:
            matching_bin = bin_files[0]
        return cue, matching_bin

    if iso_files:
        return None, iso_files[0]
    if bin_files:
        return None, bin_files[0]
    return None, None


def create_minimal_cue(bin_path):
    cue_path = os.path.splitext(bin_path)[0] + ".cue"
    bin_name = os.path.basename(bin_path)
    size = os.path.getsize(bin_path)
    if size % 2352 == 0:
        mode = "MODE2/2352"
    elif size % 2048 == 0:
        mode = "MODE1/2048"
    else:
        mode = "MODE2/2352"
    cue_content = f'FILE "{bin_name}" BINARY\n  TRACK 01 {mode}\n    INDEX 01 00:00:00\n'
    with open(cue_path, "w", encoding="utf-8") as f:
        f.write(cue_content)
    return cue_path


def convert_to_chd(input_file, output_chd):
    cmd = [CHDMAN, "createcd", "--input", input_file, "--output", output_chd, "--force"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if result.returncode == 0 and os.path.exists(output_chd):
            size = os.path.getsize(output_chd)
            if size > 1024 * 1024:
                log(f"  CHD criado: {size/1024/1024:.1f} MB")
                return True
            else:
                log(f"  CHD muito pequeno: {size} bytes")
                if os.path.exists(output_chd):
                    os.remove(output_chd)
                return False
        else:
            log(f"  chdman falhou (rc={result.returncode}): {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        log(f"  chdman timeout")
        return False
    except Exception as e:
        log(f"  Erro na conversao: {e}")
        return False


def cleanup(archive_path, extract_dir):
    for p in [archive_path, extract_dir]:
        if p and os.path.exists(p):
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
            elif os.path.isdir(p):
                subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", p], capture_output=True)


def process_game(session, game, progress):
    serial = game["serial"]
    title = game["title"]
    region = game["region"]

    existing = chd_exists(serial)
    if existing:
        log(f"Pular {serial} - CHD ja existe: {existing}")
        progress["completed"][serial] = {"chd": existing, "title": title}
        return "skip"

    # Try Archive.org first (more reliable than Romulation)
    archive_path, is_chd = download_from_archive_org(serial, title, region)

    # Fallback to Romulation
    if not archive_path:
        archive_path = download_from_romulation(session, serial, title, region)
        is_chd = False

    if not archive_path:
        log(f"FALHOU {serial} - download nao concluido em nenhuma fonte")
        progress["failed"][serial] = {"title": title, "reason": "download_failed_all_sources"}
        return "failed"

    # If archive.org returned a CHD directly, it's already in the right place
    if is_chd:
        size = os.path.getsize(archive_path)
        if size > 1024 * 1024:
            log(f"  CHD direto do archive.org: {archive_path}")
            progress["completed"][serial] = {"chd": archive_path, "title": title, "source": "archive_chd"}
            return "ok"
        else:
            log(f"  CHD muito pequeno, removendo")
            os.remove(archive_path)
            progress["failed"][serial] = {"title": title, "reason": "chd_too_small"}
            return "failed"

    # Extract
    extract_dir = os.path.join(DL_DIR, f"{serial}_extract")
    if os.path.exists(extract_dir):
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", extract_dir], capture_output=True)

    log(f"  Extraindo...")
    extracted = extract_archive(archive_path, extract_dir)
    if not extracted:
        log(f"FALHOU {serial} - extracao sem arquivos")
        progress["failed"][serial] = {"title": title, "reason": "extraction_failed"}
        cleanup(archive_path, extract_dir)
        return "failed"

    cue_file, bin_or_iso = find_disc_files(extracted)
    if not bin_or_iso and not cue_file:
        log(f"FALHOU {serial} - nenhum .cue/.iso/.bin")
        progress["failed"][serial] = {"title": title, "reason": "no_disc_file"}
        cleanup(archive_path, extract_dir)
        return "failed"

    if cue_file:
        input_file = cue_file
    else:
        if bin_or_iso.lower().endswith(".bin"):
            input_file = create_minimal_cue(bin_or_iso)
        else:
            input_file = bin_or_iso

    safe_title = sanitize_name(title)
    chd_name = f"{safe_title}-{serial}.chd"
    chd_path = os.path.join(CHD_DIR, chd_name)

    log(f"  Convertendo: {chd_name}")
    ok = convert_to_chd(input_file, chd_path)
    if ok:
        progress["completed"][serial] = {"chd": chd_path, "title": title}
        cleanup(archive_path, extract_dir)
        return "ok"
    else:
        progress["failed"][serial] = {"title": title, "reason": "chd_conversion_failed"}
        cleanup(archive_path, extract_dir)
        return "failed"


# === MAIN ===
def main():
    acquire_lock()
    try:
        log("=" * 60)
        log("PSX ROM Downloader iniciado (Archive.org + Romulation)")
        log("=" * 60)

        os.makedirs(DL_DIR, exist_ok=True)
        os.makedirs(CHD_DIR, exist_ok=True)

        games = load_list()
        log(f"Lista: {len(games)} jogos (sem demos)")

        progress = load_progress()
        log(f"Progresso: {len(progress.get('completed', {}))} completos, "
            f"{len(progress.get('failed', {}))} falhados")

        session = requests.Session()
        session.headers.update(HEADERS)

        stats = {"ok": 0, "failed": 0, "skip": 0}
        start_idx = progress.get("last_index", 0)

        for i, game in enumerate(games):
            if i < start_idx:
                continue

            serial = game["serial"]
            if serial in progress.get("completed", {}):
                continue

            log(f"\n--- [{i+1}/{len(games)}] {serial} - {game['title']} [{game['region']}] ---")

            try:
                result = process_game(session, game, progress)
                stats[result] = stats.get(result, 0) + 1
            except Exception as e:
                log(f"  EXCECAO: {e}")
                progress["failed"][serial] = {"title": game["title"], "reason": f"exception: {e}"}
                stats["failed"] += 1

            progress["last_index"] = i + 1
            save_progress(progress)

            # Delay between games to be polite to archive.org
            if i < len(games) - 1:
                time.sleep(ARCHIVE_DELAY)

        log("\n" + "=" * 60)
        log(f"CONCLUIDO. Stats: {stats}")
        log(f"Total completos: {len(progress.get('completed', {}))}")
        log(f"Total falhados: {len(progress.get('failed', {}))}")
        log("=" * 60)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
