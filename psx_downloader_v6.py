#!/usr/bin/env python3
"""
PSX ROM Downloader - Vimm.net + Romspedia fallback
Baixa jogos PSX faltantes e converte para CHD.
"""
import sys
import os
import re
import json
import time
import subprocess
import shutil
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ============ CONFIG ============
LISTA_FILE = r'F:\importre_state\lista_ainda_faltam.txt'
PROGRESS_FILE = r'F:\importre_state\download_progress_v6.json'
CHD_OUTPUT_DIR = r'F:\testes'
DOWNLOAD_DIR = r'F:\downloads\psx_faltantes'
CHDMAN = r'F:\importre\chdman.exe'
SEVENZIP = r'C:\Program Files\7-Zip\7z.exe'
VIMM_CACHE_FILE = r'F:\importre_state\vimm_cache_v2.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

REGION_ORDER = {'USA': 0, 'PAL': 1, 'JPN': 2, 'HBREW': 3}
REGION_MAP = {
    'USA': ['USA', 'usa.png'],
    'PAL': ['PAL', 'europe.png', 'europeanunion.png', 'uk.png', 'germany.png', 'france.png', 'spain.png', 'italy.png'],
    'JPN': ['JPN', 'japan.png'],
}

# ============ HELPERS ============

def load_progress():
    """Carrega progresso salvo."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'completed': {}, 'failed': {}, 'skipped': {}}

def save_progress(progress):
    """Salva progresso."""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

def load_vimm_cache():
    """Carrega cache de vault IDs do Vimm."""
    if os.path.exists(VIMM_CACHE_FILE):
        with open(VIMM_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_vimm_cache(cache):
    """Salva cache do Vimm."""
    with open(VIMM_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def parse_list():
    """Parseia a lista de faltantes.
    Formato: N. SERIAL - NOME [REGIAO]
    """
    games = []
    with open(LISTA_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Pattern: N. SERIAL - NOME [REGIAO]
            m = re.match(r'^(\d+)\.\s+(\S+)\s*-\s*(.+?)\s*\[(\w+)\]\s*$', line)
            if m:
                num = int(m.group(1))
                serial = m.group(2)
                name = m.group(3).strip()
                region = m.group(4).strip()
                games.append({
                    'num': num,
                    'serial': serial,
                    'name': name,
                    'region': region,
                    'line': line,
                })
            else:
                print(f'  WARN: não consegui parsear: {line}')
    return games

def clean_title_for_search(name):
    """Limpa o título para busca no Vimm."""
    # Remove annotations entre parênteses e colchetes
    title = re.sub(r'\[.*?\]', '', name)
    title = re.sub(r'\(.*?\)', '', title)
    # Remove Disc info
    title = re.sub(r'Disc\s*\d+\s*of\s*\d+', '', title, flags=re.I)
    title = re.sub(r'Disc\s*\d+', '', title, flags=re.I)
    # Remove trailing punctuation/whitespace
    title = title.strip(' -')
    # Pega apenas as primeiras 6 palavras
    words = title.split()
    if len(words) > 6:
        title = ' '.join(words[:6])
    return title

def sanitize_filename(name):
    """Sanitiza nome para arquivo."""
    name = re.sub(r'[^\w\-]', '-', name)
    name = re.sub(r'-+', '-', name)
    name = name.strip('-')
    return name

def is_demo(name):
    """Verifica se é demo."""
    demo_keywords = ['demo', 'trial', 'sample', 'taikenban', 'preview', 'net yaroze',
                     'jampack', 'kiosk', 'promotional', 'calpis', 'pocket zanmai']
    name_lower = name.lower()
    for kw in demo_keywords:
        if kw in name_lower:
            return True
    return False

# ============ VIMM.NET ============

def vimm_search(session, title, system='PS1'):
    """Busca jogo no Vimm.net e retorna lista de resultados.
    Retorna: [{'vault_id': 'NNNN', 'title': '...', 'system': 'PS1', 'region': 'USA', 'version': '1.0'}]
    """
    results = []
    url = f'https://vimm.net/vault/?p=list&q={quote(title)}'
    try:
        r = session.get(url, timeout=30)
        if r.status_code != 200:
            return results
    except Exception as e:
        print(f'    Vimm search error: {e}')
        return results

    soup = BeautifulSoup(r.text, 'html.parser')
    # Parse the results table
    table = soup.find('table', class_='rounded')
    if not table:
        return results

    for tr in table.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) < 3:
            continue
        sys_name = tds[0].get_text(strip=True)
        # Find the vault link - skip /vault/999999 (hidden placeholder)
        vault_id = None
        game_title = ''
        for a in tds[1].find_all('a', href=True):
            href = a['href']
            if '/vault/' in href:
                vid = href.split('/vault/')[-1].split('"')[0].split("'")[0].split('&')[0]
                if vid.isdigit() and vid != '999999':
                    vault_id = vid
                    game_title = a.get_text(strip=True)
                    break
        if not vault_id:
            continue
        # Region from flag image
        region = 'Unknown'
        region_imgs = tds[2].find_all('img')
        for img in region_imgs:
            src = img.get('src', '')
            title_attr = img.get('title', '')
            if 'usa' in src.lower() or title_attr == 'USA':
                region = 'USA'
            elif 'europe' in src.lower() or 'europeanunion' in src.lower() or title_attr in ['Europe', 'EU']:
                region = 'PAL'
            elif 'japan' in src.lower() or title_attr == 'Japan':
                region = 'JPN'
        # Version
        version = tds[3].get_text(strip=True) if len(tds) > 3 else ''

        results.append({
            'vault_id': vault_id,
            'title': game_title,
            'system': sys_name,
            'region': region,
            'version': version,
        })

    return results

def vimm_get_media_id(session, vault_id):
    """Obtém o mediaId da página do jogo no Vimm."""
    url = f'https://vimm.net/vault/{vault_id}'
    try:
        r = session.get(url, timeout=30)
        if r.status_code != 200:
            return None, None
    except Exception as e:
        print(f'    Vimm game page error: {e}')
        return None, None

    # Find mediaId in the download form
    m = re.search(r'name=["\']mediaId["\']\s+value=["\'](\d+)["\']', r.text, re.I)
    if not m:
        m = re.search(r'value=["\'](\d+)["\']\s+name=["\']mediaId["\']', r.text, re.I)
    if not m:
        # Try broader search
        m = re.search(r'mediaId.*?value=["\'](\d+)["\']', r.text, re.I)

    media_id = m.group(1) if m else None

    # Also get the platform
    platform = None
    soup = BeautifulSoup(r.text, 'html.parser')
    section = soup.find('div', class_='sectionTitle')
    if section:
        platform = section.get_text(strip=True)

    # Check if download is available (not upload-only)
    upload_only = 'Download unavailable' in r.text

    return media_id, platform

def vimm_download(session, media_id, dest_path, vault_id=None):
    """Faz GET para dl3.vimm.net com mediaId e baixa o arquivo."""
    url = f'https://dl3.vimm.net/?mediaId={media_id}'
    headers = {}
    if vault_id:
        headers['Referer'] = f'https://vimm.net/vault/{vault_id}'
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            r = session.get(url, stream=True, timeout=300, allow_redirects=True, headers=headers)
            if r.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f'    HTTP 429 (rate limited). Aguardando {wait}s...')
                time.sleep(wait)
                continue
            if r.status_code != 200:
                print(f'    Download HTTP {r.status_code}')
                return False

            content_type = r.headers.get('content-type', '')
            content_disp = r.headers.get('content-disposition', '')
            print(f'    Content-Type: {content_type}, Content-Disposition: {content_disp[:80]}')

            # Check if we got HTML instead of a file
            if 'text/html' in content_type:
                print(f'    Got HTML instead of file (likely error page)')
                return False

            # Check for Demo in filename
            if 'demo' in content_disp.lower():
                print(f'    [SKIP] Arquivo é DEMO: {content_disp[:100]}')
                return False

            total = 0
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=256 * 1024):
                    f.write(chunk)
                    total += len(chunk)

            size = os.path.getsize(dest_path)
            print(f'    Downloaded: {size} bytes ({size/1024/1024:.1f} MB)')
            if size < 1024:
                with open(dest_path, 'r', errors='ignore') as f:
                    print(f'    Content: {f.read()[:300]}')
                os.remove(dest_path)
                return False
            return True
        except Exception as e:
            print(f'    Download error: {e}')
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False
    return False

def find_ps1_match(results, target_region, target_title=''):
    """Encontra o resultado PS1 que melhor corresponde.
    Filtra demos e prefere match exato de título.
    """
    ps1_results = [r for r in results if r['system'] in ('PS1', 'PlayStation')]
    if not ps1_results:
        return None

    # Filter out demos
    ps1_results = [r for r in ps1_results if not is_demo(r['title'])]
    if not ps1_results:
        return None

    # Clean target title for comparison
    target_lower = re.sub(r'[^a-z0-9]', '', target_title.lower()) if target_title else ''

    # Score each result by title similarity
    def score(r):
        r_lower = re.sub(r'[^a-z0-9]', '', r['title'].lower())
        # Exact match
        if r_lower == target_lower:
            base = 100
        # Target is substring of result or vice versa
        elif target_lower and (target_lower in r_lower or r_lower in target_lower):
            base = 50
        # Word overlap
        else:
            target_words = set(re.sub(r'[^a-z0-9 ]', '', target_title.lower()).split()) if target_title else set()
            r_words = set(re.sub(r'[^a-z0-9 ]', '', r['title'].lower()).split())
            overlap = len(target_words & r_words)
            base = overlap * 10
        # Region bonus
        if target_region and r['region'] == target_region:
            base += 20
        return base

    ps1_results.sort(key=score, reverse=True)
    return ps1_results[0] if ps1_results else None

# ============ ROMSPEDIA ============

def romspedia_search(session, title):
    """Busca no Romspedia. Retorna URL de download ou None."""
    # Try multiple URL formats
    urls = [
        f'https://www.romspedia.com/roms/playstation?q={quote(title)}',
        f'https://www.romspedia.com/roms/psx?q={quote(title)}',
        f'https://www.romspedia.com/psx-roms?q={quote(title)}',
    ]
    for url in urls:
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                # Find game links
                soup = BeautifulSoup(r.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    text = a.get_text(strip=True).lower()
                    if '/rom/' in href and any(w in text for w in title.lower().split()[:2]):
                        full_url = urljoin('https://www.romspedia.com/', href)
                        return full_url
        except Exception as e:
            print(f'    Romspedia search error: {e}')
            continue
    return None

def romspedia_download(session, game_url, dest_path):
    """Tenta baixar do Romspedia."""
    try:
        r = session.get(game_url, timeout=30)
        if r.status_code != 200:
            return False
        # Find download link
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'download' in href.lower():
                dl_url = urljoin('https://www.romspedia.com/', href)
                r2 = session.get(dl_url, stream=True, timeout=300, allow_redirects=True)
                if r2.status_code == 200 and 'text/html' not in r2.headers.get('content-type', ''):
                    with open(dest_path, 'wb') as f:
                        for chunk in r2.iter_content(chunk_size=256 * 1024):
                            f.write(chunk)
                    size = os.path.getsize(dest_path)
                    if size > 1024:
                        return True
                    os.remove(dest_path)
    except Exception as e:
        print(f'    Romspedia download error: {e}')
    return False

# ============ EXTRACTION & CHD ============

def extract_archive(archive_path, dest_dir):
    """Extrai arquivo .7z, .zip ou .rar com 7-Zip."""
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    cmd = [SEVENZIP, 'x', archive_path, f'-o{dest_dir}', '-y', '-aos']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f'    7z error: {result.stderr[:200]}')
        return False
    return True

def find_cue_bin(directory):
    """Encontra arquivos .cue e .bin recursivamente."""
    cue_files = []
    bin_files = []
    for root, dirs, files in os.walk(directory):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext == '.cue':
                cue_files.append(os.path.join(root, f))
            elif ext == '.bin':
                bin_files.append(os.path.join(root, f))
            elif ext == '.iso':
                bin_files.append(os.path.join(root, f))
    return cue_files, bin_files

def create_cue_file(cue_path, bin_name):
    """Cria arquivo .cue para um .bin."""
    with open(cue_path, 'w', encoding='utf-8') as f:
        f.write(f'FILE "{bin_name}" BINARY\n')
        f.write('  TRACK 01 MODE2/2352\n')
        f.write('    INDEX 01 00:00:00\n')
    return cue_path

def convert_to_chd(cue_path, chd_output):
    """Converte .cue+.bin para CHD usando chdman."""
    cmd = [CHDMAN, 'createcd', '--input', cue_path, '--output', chd_output, '--force']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f'    chdman error: {result.stderr[:300]}')
        # Try with MODE1 if MODE2 failed
        return False
    return os.path.exists(chd_output) and os.path.getsize(chd_output) > 1024

def process_game(session, game, progress, vimm_cache):
    """Processa um jogo: busca, baixa, extrai, converte para CHD."""
    serial = game['serial']
    name = game['name']
    region = game['region']

    # Check if already completed
    if serial in progress['completed']:
        print(f'  [SKIP] {serial} já completado')
        return 'skipped'

    # Skip demos
    if is_demo(name):
        print(f'  [SKIP] {serial} é demo: {name}')
        progress['skipped'][serial] = {'name': name, 'reason': 'demo'}
        return 'skipped'

    print(f'\n{"="*60}')
    print(f'  [{game["num"]}/222] {serial} - {name} [{region}]')
    print(f'{"="*60}')

    search_title = clean_title_for_search(name)
    print(f'  Buscando: "{search_title}"')

    # === TENTATIVA 1: Vimm.net ===
    # Check cache first - but only trust valid entries
    cache_key = f'{serial}'
    cached = vimm_cache.get(cache_key)
    if cached and cached.get('vault_id') and cached['vault_id'] != '999999' and cached.get('media_id'):
        vault_id = cached['vault_id']
        media_id = cached.get('media_id')
        print(f'  [CACHE] Vimm: vault/{vault_id}, mediaId={media_id}')
        # Try download with cached media_id
        dest = os.path.join(DOWNLOAD_DIR, f'{serial}.7z')
        if vimm_download(session, media_id, dest, vault_id):
            if process_download(dest, serial, name, game):
                progress['completed'][serial] = {
                    'name': name, 'region': region,
                    'source': 'vimm_cache', 'vault_id': vault_id, 'media_id': media_id
                }
                save_progress(progress)
                return 'completed'
    else:
        # Search Vimm fresh
        time.sleep(3)  # Rate limit
        results = vimm_search(session, search_title)
        print(f'  Vimm: {len(results)} resultados')

        # Filter for PS1 and sort by score
        ps1_results = [r for r in results if r['system'] in ('PS1', 'PlayStation')]
        # Filter out demos from title
        ps1_results = [r for r in ps1_results if not is_demo(r['title'])]
        if ps1_results:
            # Sort by score
            target_lower = re.sub(r'[^a-z0-9]', '', search_title.lower())
            def score(r):
                r_lower = re.sub(r'[^a-z0-9]', '', r['title'].lower())
                if r_lower == target_lower:
                    base = 100
                elif target_lower and (target_lower in r_lower or r_lower in target_lower):
                    base = 50
                else:
                    target_words = set(re.sub(r'[^a-z0-9 ]', '', search_title.lower()).split())
                    r_words = set(re.sub(r'[^a-z0-9 ]', '', r['title'].lower()).split())
                    base = len(target_words & r_words) * 10
                if region and r['region'] == region:
                    base += 20
                return base
            ps1_results.sort(key=score, reverse=True)

            print(f'  Vimm PS1: {len(ps1_results)} resultados')
            for r in ps1_results[:5]:
                print(f'    -> /vault/{r["vault_id"]} | {r["title"]} | {r["region"]} | v{r["version"]}')

            # Try each match until we find a non-demo download
            for match in ps1_results[:5]:  # Try up to 5 matches
                vault_id = match['vault_id']
                print(f'  Tentando: /vault/{vault_id} ({match["title"]})')

                time.sleep(3)  # Rate limit
                media_id, platform = vimm_get_media_id(session, vault_id)
                if media_id:
                    print(f'  mediaId: {media_id}, Platform: {platform}')
                    vimm_cache[cache_key] = {
                        'vault_id': vault_id, 'media_id': media_id,
                        'title': match['title'], 'platform': platform
                    }
                    save_vimm_cache(vimm_cache)

                    # Download
                    dest = os.path.join(DOWNLOAD_DIR, f'{serial}.7z')
                    time.sleep(10)  # Longer delay to avoid rate limiting
                    if vimm_download(session, media_id, dest, vault_id):
                        if process_download(dest, serial, name, game):
                            progress['completed'][serial] = {
                                'name': name, 'region': region,
                                'source': 'vimm', 'vault_id': vault_id, 'media_id': media_id
                            }
                            save_progress(progress)
                            return 'completed'
                    else:
                        print(f'  Download falhou (demo ou erro), tentando próximo...')
                        continue
                else:
                    print(f'  Sem mediaId na página')
                    continue
        else:
            print(f'  Vimm: nenhum resultado PS1')
            vimm_cache[cache_key] = {'status': 'not_found'}
            save_vimm_cache(vimm_cache)

    # === TENTATIVA 2: Romspedia ===
    print(f'  Tentando Romspedia...')
    time.sleep(2)
    romspedia_url = romspedia_search(session, search_title)
    if romspedia_url:
        print(f'  Romspedia: {romspedia_url}')
        dest = os.path.join(DOWNLOAD_DIR, f'{serial}_romspedia.7z')
        if romspedia_download(session, romspedia_url, dest):
            if process_download(dest, serial, name, game):
                progress['completed'][serial] = {
                    'name': name, 'region': region, 'source': 'romspedia'
                }
                save_progress(progress)
                return 'completed'
    else:
        print(f'  Romspedia: não encontrado')

    # === FALHOU ===
    print(f'  [FAILED] {serial} - todas as fontes falharam')
    progress['failed'][serial] = {
        'name': name, 'region': region,
        'reason': 'all sources failed'
    }
    save_progress(progress)
    return 'failed'

def process_download(archive_path, serial, name, game):
    """Extrai arquivo baixado e converte para CHD."""
    if not os.path.exists(archive_path):
        return False

    # Create extraction directory
    extract_dir = os.path.join(DOWNLOAD_DIR, f'{serial}_extract')
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir, ignore_errors=True)

    print(f'  Extraindo: {archive_path}')
    if not extract_archive(archive_path, extract_dir):
        print(f'  Falha na extração')
        return False

    # Find .cue and .bin files
    cue_files, bin_files = find_cue_bin(extract_dir)
    print(f'  Encontrados: {len(cue_files)} .cue, {len(bin_files)} .bin')

    if not cue_files and not bin_files:
        print(f'  Nenhum .cue ou .bin encontrado')
        # List what we got
        for root, dirs, files in os.walk(extract_dir):
            for f in files[:10]:
                print(f'    {os.path.join(root, f)}')
        return False

    # Determine CHD output name
    # Format: Name-Serial.chd (sanitized)
    chd_name = sanitize_filename(name)
    # Remove Disc info from name for CHD
    chd_name = re.sub(r'-Disc\d+of\d+', '', chd_name, flags=re.I)
    chd_name = re.sub(r'-Disc\d+', '', chd_name, flags=re.I)
    chd_output = os.path.join(CHD_OUTPUT_DIR, f'{chd_name}-{serial}.chd')

    # Handle multi-disc
    if len(cue_files) > 1:
        # Take first disc
        print(f'  Multi-disco: usando primeiro .cue')
        cue_path = cue_files[0]
    elif len(cue_files) == 1:
        cue_path = cue_files[0]
    else:
        # No .cue, create one for first .bin
        if bin_files:
            bin_path = bin_files[0]
            bin_name = os.path.basename(bin_path)
            cue_path = os.path.splitext(bin_path)[0] + '.cue'
            create_cue_file(cue_path, bin_name)
            print(f'  .cue criado: {cue_path}')
        else:
            print(f'  Sem arquivos para converter')
            return False

    # Convert to CHD
    print(f'  Convertendo: {cue_path} -> {chd_output}')
    if convert_to_chd(cue_path, chd_output):
        size = os.path.getsize(chd_output)
        print(f'  [OK] CHD criado: {chd_output} ({size/1024/1024:.1f} MB)')
        # Cleanup extraction dir
        shutil.rmtree(extract_dir, ignore_errors=True)
        # Remove archive
        if os.path.exists(archive_path):
            os.remove(archive_path)
        return True
    else:
        print(f'  [FAIL] Conversão CHD falhou')
        # Try with MODE1/2048
        if bin_files:
            bin_path = bin_files[0]
            bin_name = os.path.basename(bin_path)
            cue_path2 = os.path.splitext(bin_path)[0] + '_mode1.cue'
            with open(cue_path2, 'w', encoding='utf-8') as f:
                f.write(f'FILE "{bin_name}" BINARY\n')
                f.write('  TRACK 01 MODE1/2048\n')
                f.write('    INDEX 01 00:00:00\n')
            print(f'  Tentando MODE1/2048...')
            if convert_to_chd(cue_path2, chd_output):
                size = os.path.getsize(chd_output)
                print(f'  [OK] CHD criado (MODE1): {chd_output} ({size/1024/1024:.1f} MB)')
                shutil.rmtree(extract_dir, ignore_errors=True)
                if os.path.exists(archive_path):
                    os.remove(archive_path)
                return True
        return False

# ============ MAIN ============

def main():
    print('='*60)
    print('  PSX ROM Downloader v6 - Vimm.net + Romspedia')
    print('='*60)

    # Ensure directories exist
    os.makedirs(CHD_OUTPUT_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Load data
    games = parse_list()
    print(f'  Total de jogos na lista: {len(games)}')

    progress = load_progress()
    print(f'  Completados: {len(progress.get("completed", {}))}')
    print(f'  Falharam: {len(progress.get("failed", {}))}')
    print(f'  Skipped: {len(progress.get("skipped", {}))}')

    vimm_cache = load_vimm_cache()
    print(f'  Cache Vimm: {len(vimm_cache)} entradas')

    # Sort by region priority
    games.sort(key=lambda g: (REGION_ORDER.get(g['region'], 99), g['num']))

    # Create session
    session = requests.Session()
    session.headers.update(HEADERS)

    # Process each game
    completed_count = 0
    failed_count = 0
    skipped_count = 0

    for game in games:
        try:
            result = process_game(session, game, progress, vimm_cache)
            if result == 'completed':
                completed_count += 1
            elif result == 'failed':
                failed_count += 1
            elif result == 'skipped':
                skipped_count += 1
        except Exception as e:
            print(f'  [ERROR] {game["serial"]}: {e}')
            progress['failed'][game['serial']] = {
                'name': game['name'], 'region': game['region'],
                'reason': f'exception: {str(e)[:200]}'
            }
            save_progress(progress)
            failed_count += 1

        # Print summary so far
        total_done = completed_count + failed_count + skipped_count
        print(f'\n  --- Resumo: {total_done}/{len(games)} | OK={completed_count} FAIL={failed_count} SKIP={skipped_count} ---')

    # Final summary
    print(f'\n{"="*60}')
    print(f'  RESUMO FINAL')
    print(f'  Total: {len(games)}')
    print(f'  Completados: {completed_count}')
    print(f'  Falharam: {failed_count}')
    print(f'  Skipped: {skipped_count}')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()
