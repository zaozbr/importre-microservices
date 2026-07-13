"""
Busca ROMs via Google dorking: site:archive.org "SLUS-01234"
Também busca em outras fontes: Vimm's Lair, CDromance, EdgeROM.
"""
import sys, os, time, json, re
from urllib.parse import quote, unquote
import requests
import urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STATE_DIR = r"D:\roms\library\roms\_importre_state"

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})


def google_search(query, num=10):
    """Busca no Google e retorna resultados (URL, título)."""
    url = f"https://www.google.com/search?q={quote(query)}&num={num}"
    try:
        r = s.get(url, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            results = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/url?q='):
                    real_url = unquote(href.split('/url?q=')[1].split('&')[0])
                    title = a.get_text(strip=True)
                    if real_url.startswith('http') and 'google.com' not in real_url:
                        results.append((real_url, title))
            return results[:num]
    except:
        pass
    return []


def search_archive_google(serial):
    """Busca serial no archive.org via Google."""
    query = f'site:archive.org "{serial}"'
    results = google_search(query)
    archive_results = []
    for url, title in results:
        if 'archive.org' in url:
            # Extrair identifier da URL
            # http://archive.org/details/IDENTIFIER ou /download/IDENTIFIER
            match = re.search(r'archive\.org/(?:details|download)/([^/]+)', url)
            if match:
                ident = match.group(1)
                archive_results.append((ident, title, url))
    return archive_results


def search_vimm(serial, name=''):
    """Busca no Vimm's Lair."""
    # Vimm tem API de busca
    url = f"https://vimm.net/vault/?search={quote(serial)}"
    try:
        r = s.get(url, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Procurar links para páginas de ROM
            for a in soup.find_all('a', href=True):
                if '/vault/' in a['href'] and 'search' not in a['href']:
                    href = a['href']
                    title = a.get_text(strip=True)
                    if serial.lower() in title.lower() or serial.lower() in href.lower():
                        return f"https://vimm.net{href}", title
    except:
        pass
    return None, None


def search_cdromance(serial, name=''):
    """Busca no CDromance."""
    url = f"https://cdromance.org/?s={quote(serial)}"
    try:
        r = s.get(url, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                title = a.get_text(strip=True)
                if 'cdromance.org' in href and serial.lower() in title.lower():
                    return href, title
    except:
        pass
    return None, None


def search_doperoms(serial, name=''):
    """Busca em DopeROMs."""
    url = f"https://www.doperoms.com/search.php?search={quote(serial)}&system=Playstation"
    try:
        r = s.get(url, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                title = a.get_text(strip=True)
                if serial.lower() in title.lower():
                    if not href.startswith('http'):
                        href = f"https://www.doperoms.com{href}"
                    return href, title
    except:
        pass
    return None, None


def search_romulation_api(serial):
    """Busca na API do Romulation."""
    url = f"https://www.romulation.org/api/search?q={quote(serial)}&platform=psx"
    try:
        r = s.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                return data[0].get('download_url') or data[0].get('url'), data[0].get('title', '')
    except:
        pass
    return None, None


def search_all_sources(serial, name=''):
    """Busca em todas as fontes criativas. Retorna lista de (source, url, title)."""
    results = []

    # 1. Google dorking no archive.org
    archive_hits = search_archive_google(serial)
    for ident, title, url in archive_hits[:3]:
        results.append(('archive_google', url, title))

    # 2. Vimm's Lair
    vimm_url, vimm_title = search_vimm(serial, name)
    if vimm_url:
        results.append(('vimm', vimm_url, vimm_title))

    # 3. CDromance
    cd_url, cd_title = search_cdromance(serial, name)
    if cd_url:
        results.append(('cdromance', cd_url, cd_title))

    # 4. DopeROMs
    dr_url, dr_title = search_doperoms(serial, name)
    if dr_url:
        results.append(('doperoms', dr_url, dr_title))

    # 5. Romulation API
    rom_url, rom_title = search_romulation_api(serial)
    if rom_url:
        results.append(('romulation', rom_url, rom_title))

    return results


def main():
    print("=" * 60, flush=True)
    print("GOOGLE DORK + MULTI-SOURCE SEARCH", flush=True)
    print("=" * 60, flush=True)

    QUEUE_PATH = os.path.join(STATE_DIR, "queue.json")
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)

    pending = q.get('queue', [])
    completed = q.get('completed', {})
    if not isinstance(completed, dict):
        completed = {}
    failed = q.get('failed', {})
    if not isinstance(failed, dict):
        failed = {}

    seen = set()
    to_search = []
    for item in pending:
        if isinstance(item, dict):
            sr = item.get('serial', '')
            if sr and sr not in seen and sr not in completed:
                seen.add(sr)
                to_search.append(item)
    for sr, info in failed.items():
        if sr not in seen:
            seen.add(sr)
            to_search.append({'serial': sr, 'name': info.get('name', '')})

    print(f"Buscando {len(to_search)} ROMs em fontes criativas...\n", flush=True)

    all_results = {}
    for item in to_search:
        serial = item.get('serial', '')
        name = item.get('name', '')
        print(f"=== {serial} ({name[:30]}) ===", flush=True)

        hits = search_all_sources(serial, name)
        if hits:
            all_results[serial] = []
            for source, url, title in hits:
                print(f"  [{source}] {title[:50]} -> {url[:80]}", flush=True)
                all_results[serial].append({'source': source, 'url': url, 'title': title})
        else:
            print(f"  Nenhuma fonte encontrou", flush=True)

        time.sleep(1)  # Rate limit para Google

    # Salvar
    results_path = os.path.join(STATE_DIR, "google_dork_results.json")
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nResultados salvos em: {results_path}", flush=True)
    print(f"Total: {sum(len(v) for v in all_results.values())} hits em {len(all_results)} ROMs", flush=True)


if __name__ == '__main__':
    main()
