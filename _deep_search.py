"""
Deep Search - Busca criativa em camadas com variacoes de termos.

Estrategia: Em vez de buscar apenas por serial/nome em sites de ROMs,
esta busca explora fontes NAO utilizadas pelo sistema atual:

1. GitHub: Repositorios com listas de ROMs, links, dat files
2. Archive.org: Colecoes nao indexadas, com variacoes de nome
3. Wayback Machine: Links expirados de sites conhecidos
4. Bing: Busca com site: especifico (github, archive.org, reddit, pastebin)
5. nyaa.si: Tracker japones para jogos JP (magnet/HTTP)

E gera VARIACOES DE TERMOS (sub-termos) para cada item:
- Nome original
- Nome sem artigos/preposicoes
- Serial sem hifen / com underscore
- Abreviacoes comuns (Vol -> V, Series -> Ser)
- Nome em romaji (se aplicavel)
- Combinacoes de termos significativos

Cada variacao e testada em cada fonte, criando uma matriz de busca
que cobre muito mais terreno que a busca linear atual.
"""
import json, os, re, time, hashlib, threading
from urllib.parse import quote, quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Timeout global para todas as requisicoes
REQUEST_TIMEOUT = 12  # segundos
ARCHIVE_TIMEOUT = 15  # archive.org via proxy WARP pode ser mais lento

STATE_DIR = r'D:\roms\library\roms\_importre_state'
PSXDC_INDEX = os.path.join(STATE_DIR, 'psxdc_index.json')
DEEP_CACHE = os.path.join(STATE_DIR, 'deep_search_cache.json')
DEEP_LOG = os.path.join(STATE_DIR, 'deep_search.log')

# Proxy Tor para acessar archive.org (bloqueado sem proxy)
# Tor roda como SOCKS5 na porta 9050 (iniciado por _start_tor.py)
TOR_PROXY = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}

# Verificar se Tor esta ativo
def _tor_available():
    """Verifica se o proxy Tor esta respondendo."""
    try:
        r = requests.get('https://archive.org/advancedsearch.php?q=test&output=json',
                        timeout=10, proxies=TOR_PROXY)
        return r.status_code == 200
    except:
        return False

# Sessao com proxy para archive.org
def _get_session(use_proxy=False):
    """Cria uma sessao requests com ou sem proxy."""
    s = requests.Session()
    s.headers.update(HEADERS)
    if use_proxy:
        s.proxies = TOR_PROXY
    return s

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ja;q=0.8',
}

# Sites de ROMs conhecidos para extrair links de resultados de busca
KNOWN_ROM_SITES = [
    'archive.org', 'coolrom.com', 'romsfun.com', 'romspedia.com',
    'vimm.net', 'retrostic.com', 'romsdl.com', 'blueroms.ws',
    'romsretro.com', 'romsgames.net', 'retromania.gg', 'hexrom.com',
    'consoleroms.com', 'romulation.org', 'cdromance.org',
    'romhustler.org', 'romsbase.com', 'freeroms.com',
    'emuparadise.me', 'emuparadise.org', 'doperoms.com',
    'romulation.net', 'portalroms.com', 'romsmania.com',
    'roms-download.com', 'roms.xyz', 'psxroms.com',
]

# Extensoes de ROM validas
ROM_EXTS = {'.bin', '.iso', '.img', '.cue', '.chd', '.7z', '.zip', '.rar', '.ecm'}

# Flag para archive.org instavel - se falhar 5x seguidas, pular (aumentado pois WARP pode ter latencia)
_archive_fail_count = 0
_archive_fail_lock = threading.Lock()
ARCHIVE_FAIL_LIMIT = 5

def _archive_available():
    """Verifica se archive.org esta respondendo."""
    with _archive_fail_lock:
        return _archive_fail_count < ARCHIVE_FAIL_LIMIT

def _archive_failed():
    """Registra uma falha no archive.org."""
    global _archive_fail_count
    with _archive_fail_lock:
        _archive_fail_count += 1
        if _archive_fail_count == ARCHIVE_FAIL_LIMIT:
            _log(f"archive.org marcado como INSTAVEL apos {_archive_fail_count} falhas")

def _archive_success():
    """Registra sucesso no archive.org."""
    global _archive_fail_count
    with _archive_fail_lock:
        _archive_fail_count = 0

# Cache em memoria
_cache = {}
_cache_lock = threading.Lock()
_cache_loaded = False

def _log(msg):
    try:
        with open(DEEP_LOG, 'a', encoding='utf-8', errors='replace') as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except:
        pass

def _load_cache():
    global _cache, _cache_loaded
    if _cache_loaded:
        return
    with _cache_lock:
        if _cache_loaded:
            return
        try:
            with open(DEEP_CACHE, 'r', encoding='utf-8') as f:
                _cache = json.load(f)
        except:
            _cache = {}
        _cache_loaded = True

def _save_cache():
    global _cache
    try:
        with open(DEEP_CACHE, 'w', encoding='utf-8') as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
    except:
        pass

def _cache_get(key):
    _load_cache()
    with _cache_lock:
        return _cache.get(key)

def _cache_set(key, value):
    _load_cache()
    with _cache_lock:
        _cache[key] = value
        _save_cache()

# ============================================================
# RESOLVEDOR DE NOMES
# ============================================================

_serial_to_name = None
_serial_lock = threading.Lock()

def _build_serial_index():
    """Construir indice serial -> nome a partir do psxdatacenter local."""
    global _serial_to_name
    with _serial_lock:
        if _serial_to_name is not None:
            return _serial_to_name
        try:
            with open(PSXDC_INDEX, 'r', encoding='utf-8') as f:
                psxdc = json.load(f)
            _serial_to_name = {}
            for region, games in psxdc.items():
                for name, serial in games.items():
                    # Alguns seriais sao concatenados (multi-disc)
                    # ex: "SLPS-01813SLPS-01814SLPS-01815"
                    # Pegar apenas o primeiro serial
                    if serial in _serial_to_name:
                        continue
                    # Se o nome contem o proprio serial, e lixo
                    if serial in name:
                        continue
                    _serial_to_name[serial] = name
        except Exception as e:
            _log(f"Erro building serial index: {e}")
            _serial_to_name = {}
        return _serial_to_name

def resolve_name(serial):
    """Resolve o nome de um serial usando o indice local do psxdatacenter."""
    idx = _build_serial_index()
    return idx.get(serial, '')

# ============================================================
# GERADOR DE VARIACOES DE TERMOS (SUB-TERMOS)
# ============================================================

def generate_term_variations(serial, name):
    """
    Gera variacoes de termos de busca a partir de serial e nome.
    Retorna lista de queries para buscar em diferentes fontes.
    """
    variations = []
    
    # 1. Serial entre aspas (mais preciso)
    variations.append(f'"{serial}"')
    
    # 2. Serial sem hifen
    serial_nohyphen = serial.replace('-', '')
    variations.append(serial_nohyphen)
    
    # 3. Serial com underscore
    serial_underscore = serial.replace('-', '_')
    variations.append(serial_underscore)
    
    # 4. Serial com espaco
    serial_space = serial.replace('-', ' ')
    variations.append(serial_space)
    
    if name:
        # 5. Nome original
        variations.append(name)
        
        # 6. Nome sem artigos/preposicoes
        stop_words = {'the', 'a', 'an', 'of', 'no', 'to', 'ga', 'wo', 'ni', 'de', 'wa', 'he'}
        words = re.split(r'[\s\-]+', name)
        significant = [w for w in words if w.lower() not in stop_words and len(w) > 1]
        if significant and len(significant) < len(words):
            variations.append(' '.join(significant))
        
        # 7. Nome sem sufixos comuns de series
        cleaned = re.sub(r'\b(Series|Vol\.?|Volume)\b', '', name, flags=re.I)
        cleaned = re.sub(r'\b\d+\b', '', cleaned)  # remover numeros de volume
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if cleaned and cleaned != name and len(cleaned) > 3:
            variations.append(cleaned)
        
        # 8. Primeiras 2-3 palavras significativas
        if len(significant) >= 3:
            variations.append(' '.join(significant[:2]))
            variations.append(' '.join(significant[:3]))
        
        # 9. Nome + "psx" / "ps1" / "playstation"
        variations.append(f'{name} psx')
        variations.append(f'{name} ps1')
        
        # 10. Abreviacoes para series conhecidas
        # Simple 1500 Series Vol.XX -> Simple 1500 Vol XX
        if 'Simple 1500' in name:
            vol_match = re.search(r'Vol\.?\s*(\d+)', name)
            if vol_match:
                vol = vol_match.group(1)
                # Extrair subtitulo
                subtitle = re.sub(r'.*Vol\.?\s*\d+\s*[-:]?\s*', '', name).strip()
                if subtitle:
                    variations.append(f'Simple 1500 Vol {vol} {subtitle}')
                    variations.append(f'Simple1500 Vol{vol} {subtitle}')
                    variations.append(f'Simple1500 {subtitle}')
                    # Apenas o subtitulo
                    variations.append(subtitle)
        
        # Superlite Gold Series -> Superlite Gold
        if 'Superlite' in name:
            sub = re.sub(r'.*Superlite\s*(?:Gold\s*)?Series\s*[-:]?\s*', '', name).strip()
            if sub and sub != name:
                variations.append(sub)
                variations.append(f'Superlite {sub}')
        
        # Major Wave Series -> nome sem o prefixo
        if 'Major Wave' in name:
            sub = re.sub(r'.*Major Wave\s*Series\s*[-:]?\s*', '', name).strip()
            if sub:
                variations.append(sub)
        
        # 11. Nome em romaji simplificado (remover caracteres japoneses)
        romaji = re.sub(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+', ' ', name)
        romaji = re.sub(r'\s+', ' ', romaji).strip()
        if romaji and romaji != name and len(romaji) > 3:
            variations.append(romaji)
    
    # Remover duplicatas preservando ordem
    seen = set()
    unique = []
    for v in variations:
        if v and v not in seen and len(v) > 2:
            seen.add(v)
            unique.append(v)
    
    return unique

# ============================================================
# FONTES DE BUSCA - CAMADAS NAO EXPLORADAS
# ============================================================

def search_archive_org_collections(query, serial, max_results=5):
    """
    Busca em archive.org usando a API advancedsearch.
    Diferente da busca atual, explora colecoes NAO indexadas
    e usa variacoes de termos.
    """
    if not _archive_available():
        return []
    results = []
    
    # Colecoes PSX nao indexadas pelo sistema atual
    extra_collections = [
        'Sony-Playstation',
        'PSX-Games',
        'PlayStation-1-Games',
        'sony_playstation',
        'ps1games',
        'PS1-ROMs',
        'playstation-games',
    ]
    
    # Buscar na API geral
    api_url = 'https://archive.org/advancedsearch.php'
    
    queries = [
        f'({query}) AND mediatype:(texts OR software OR movies)',
        f'({query}) AND collection:(software_library)',
        f'({query}) psx',
    ]
    
    for q in queries[:2]:  # Limitar para nao sobrecarregar
        try:
            params = {
                'q': q,
                'fl[]': ['identifier', 'title', 'description', 'downloads', 'format'],
                'rows': str(max_results),
                'output': 'json',
            }
            r = requests.get(api_url, params=params, timeout=ARCHIVE_TIMEOUT, headers=HEADERS, proxies=TOR_PROXY)
            if r.status_code == 200:
                _archive_success()
                data = r.json()
                docs = data.get('response', {}).get('docs', [])
                for doc in docs:
                    identifier = doc.get('identifier', '')
                    title = doc.get('title', '')
                    if not identifier:
                        continue
                    # Verificar se o serial esta no titulo ou identifier
                    serial_clean = serial.replace('-', '')
                    if serial in title or serial_nohyphen_in(title, serial_clean) or serial in identifier:
                        # Obter arquivos do item
                        files = _get_archive_files(identifier)
                        for f in files:
                            if any(f.lower().endswith(ext) for ext in ROM_EXTS):
                                dl_url = f'https://archive.org/download/{identifier}/{quote(f)}'
                                results.append({
                                    'url': dl_url,
                                    'source': 'archive_org_deep',
                                    'title': title,
                                    'file': f,
                                    'identifier': identifier,
                                })
                                if len(results) >= max_results:
                                    return results
        except Exception as e:
            _log(f"  archive_org_collections erro: {e}")
    
    return results

def serial_nohyphen_in(text, serial_nohyphen):
    """Verifica se serial sem hifen aparece no texto."""
    return serial_nohyphen.lower() in text.lower().replace('-', '').replace(' ', '')

def _get_archive_files(identifier):
    """Obtem lista de arquivos de um item do archive.org (via proxy WARP)."""
    if not _archive_available():
        return []
    try:
        url = f'https://archive.org/metadata/{identifier}'
        r = requests.get(url, timeout=ARCHIVE_TIMEOUT, headers=HEADERS, proxies=TOR_PROXY)
        if r.status_code == 200:
            _archive_success()
            data = r.json()
            files = data.get('files', [])
            return [f.get('name', '') for f in files if f.get('name')]
    except:
        _archive_failed()
    return []

def search_github(serial, name, max_results=5):
    """
    Busca no GitHub por serial em repositorios de ROMs.
    Usa a API de busca de codigo do GitHub.
    """
    results = []
    
    # Queries especificas para GitHub
    queries = [
        f'"{serial}" psx',
        f'"{serial}" playstation',
    ]
    
    if name:
        queries.append(f'"{serial}" "{name[:30]}"')
    
    for q in queries:
        try:
            # API de busca de codigo (nao precisa de token para busca publica, mas tem rate limit)
            url = 'https://api.github.com/search/code'
            params = {
                'q': q,
                'per_page': str(max_results),
            }
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Mozilla/5.0',
            }
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, headers=headers)
            if r.status_code == 200:
                data = r.json()
                items = data.get('items', [])
                for item in items:
                    repo = item.get('repository', {}).get('full_name', '')
                    file_name = item.get('name', '')
                    html_url = item.get('html_url', '')
                    
                    # Se for um arquivo .dat, .json, .txt, .csv com ROMs
                    if file_name.endswith(('.dat', '.json', '.txt', '.csv', '.md', '.xml')):
                        # Baixar o arquivo e procurar por links/serial
                        content = _get_github_file_content(item.get('url', ''))
                        if content:
                            found = _extract_download_from_text(content, serial, name)
                            if found:
                                results.extend(found)
                                if len(results) >= max_results:
                                    return results
            elif r.status_code == 403:
                _log(f"  GitHub rate limit (403)")
                break
        except Exception as e:
            _log(f"  github erro: {e}")
    
    return results

def _get_github_file_content(api_url):
    """Baixa conteudo de um arquivo do GitHub via API."""
    try:
        headers = {'Accept': 'application/vnd.github.v3.raw', 'User-Agent': 'Mozilla/5.0'}
        r = requests.get(api_url, timeout=REQUEST_TIMEOUT, headers=headers)
        if r.status_code == 200:
            return r.text[:50000]  # Limitar tamanho
    except:
        pass
    return ''

def _extract_download_from_text(text, serial, name):
    """Extrai URLs de download de um texto (dat, json, txt)."""
    results = []
    serial_lower = serial.lower()
    serial_nohyphen = serial.replace('-', '').lower()
    
    # Procurar por URLs que contenham o serial ou nome
    url_pattern = re.compile(r'https?://[^\s<>"\']+', re.I)
    for match in url_pattern.finditer(text):
        url = match.group(0).rstrip('.,;)')
        url_lower = url.lower()
        
        # Verificar se a URL parece ser de ROM
        if (serial_lower in url_lower or 
            serial_nohyphen in url_lower or
            any(ext in url_lower for ext in ['.bin', '.iso', '.img', '.chd', '.7z', '.zip'])):
            
            # Verificar se e de um site conhecido
            if any(site in url_lower for site in KNOWN_ROM_SITES):
                results.append({
                    'url': url,
                    'source': 'github_extract',
                    'title': f'GitHub: {serial}',
                    'file': os.path.basename(url),
                })
    
    # Procurar por archive.org identifiers
    for match in re.finditer(r'archive\.org/(?:download|details)/([a-zA-Z0-9_\-\.]+)', text, re.I):
        identifier = match.group(1)
        if serial_lower in identifier.lower() or serial_nohyphen in identifier.lower():
            # Verificar se tem arquivos de ROM
            files = _get_archive_files(identifier)
            for f in files:
                if any(f.lower().endswith(ext) for ext in ROM_EXTS):
                    dl_url = f'https://archive.org/download/{identifier}/{quote(f)}'
                    results.append({
                        'url': dl_url,
                        'source': 'github_archive',
                        'title': f'GitHub->Archive: {identifier}',
                        'file': f,
                        'identifier': identifier,
                    })
    
    return results

def search_bing_site(query, site, serial, max_results=5):
    """
    Busca no Bing com site: especifico.
    Diferente da busca google atual, usa sites NAO explorados.
    """
    results = []
    full_query = f'site:{site} {query} psx'
    
    try:
        url = f'https://www.bing.com/search'
        params = {
            'q': full_query,
            'count': str(max_results * 2),
            'setlang': 'en-US',
        }
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        if r.status_code == 200:
            # Extrair URLs dos resultados
            # Bing coloca URLs em <cite> ou <a href>
            urls_found = set()
            
            # Padrao 1: <cite>tags
            for match in re.finditer(r'<cite[^>]*>(.*?)</cite>', r.text, re.I|re.S):
                u = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                if u and not u.startswith('javascript'):
                    if not u.startswith('http'):
                        u = 'https://' + u
                    urls_found.add(u)
            
            # Padrao 2: href em resultados
            for match in re.finditer(r'href="(https?://[^"]*' + re.escape(site) + r'[^"]*)"', r.text, re.I):
                urls_found.add(match.group(1))
            
            # Filtrar URLs uteis
            for u in urls_found:
                if any(ext in u.lower() for ext in ['.bin', '.iso', '.img', '.chd', '.7z', '.zip']):
                    results.append({
                        'url': u,
                        'source': f'bing_{site}',
                        'title': f'Bing/{site}: {serial}',
                        'file': os.path.basename(u),
                    })
                elif 'archive.org' in u and '/details/' in u:
                    # Extrair identifier do archive.org
                    m = re.search(r'/details/([a-zA-Z0-9_\-\.]+)', u)
                    if m:
                        identifier = m.group(1)
                        files = _get_archive_files(identifier)
                        for f in files:
                            if any(f.lower().endswith(ext) for ext in ROM_EXTS):
                                dl_url = f'https://archive.org/download/{identifier}/{quote(f)}'
                                results.append({
                                    'url': dl_url,
                                    'source': 'bing_archive',
                                    'title': f'Bing->Archive: {identifier}',
                                    'file': f,
                                    'identifier': identifier,
                                })
                                if len(results) >= max_results:
                                    return results
    except Exception as e:
        _log(f"  bing_{site} erro: {e}")
    
    return results

def search_wayback_machine(serial, name, max_results=3):
    """
    Busca na Wayback Machine por links de ROMs em sites conhecidos
    que podem estar offline agora mas foram arquivados.
    """
    results = []
    
    # Sites para verificar na Wayback Machine
    sites_to_check = [
        ('coolrom.com', f'coolrom.com/roms/psx/'),
        ('emuparadise.me', f'emuparadise.me/psx/'),
        ('romsfun.com', f'romsfun.com/roms/'),
    ]
    
    serial_nohyphen = serial.replace('-', '')
    
    for site, path in sites_to_check:
        try:
            # API da Wayback Machine: CDX
            cdx_url = f'http://web.archive.org/cdx/search/cdx'
            params = {
                'url': f'{site}/{path}*',
                'output': 'json',
                'limit': '50',
                'filter': 'statuscode:200',
                'collapse': 'urlkey',
            }
            r = requests.get(cdx_url, params=params, timeout=REQUEST_TIMEOUT, headers=HEADERS, proxies=TOR_PROXY)
            if r.status_code == 200:
                try:
                    data = r.json()
                    if len(data) > 1:  # Primeira linha e header
                        for row in data[1:]:
                            original_url = row[2] if len(row) > 2 else ''
                            timestamp = row[1] if len(row) > 1 else ''
                            
                            # Verificar se o serial ou nome esta na URL
                            if (serial.lower() in original_url.lower() or 
                                serial_nohyphen.lower() in original_url.lower() or
                                (name and _fuzzy_url_match(name, original_url))):
                                
                                # URL da Wayback Machine
                                wb_url = f'https://web.archive.org/web/{timestamp}/{original_url}'
                                
                                # Tentar obter a pagina arquivada e extrair links de download
                                archived_page = _fetch_wayback_page(wb_url)
                                if archived_page:
                                    found = _extract_download_from_html(archived_page, serial, name)
                                    if found:
                                        results.extend(found)
                                        if len(results) >= max_results:
                                            return results
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            _log(f"  wayback_{site} erro: {e}")
    
    return results

def _fetch_wayback_page(url):
    """Busca pagina arquivada na Wayback Machine (via proxy WARP)."""
    try:
        r = requests.get(url, timeout=ARCHIVE_TIMEOUT, headers=HEADERS, proxies=TOR_PROXY)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return ''

def _extract_download_from_html(html, serial, name):
    """Extrai URLs de download de uma pagina HTML."""
    results = []
    serial_lower = serial.lower()
    
    # Procurar por links de download
    for match in re.finditer(r'href="(https?://[^"]+)"', html, re.I):
        url = match.group(1)
        url_lower = url.lower()
        
        # Links diretos de ROM
        if any(ext in url_lower for ext in ['.bin', '.iso', '.img', '.chd', '.7z', '.zip', '.ecm']):
            if serial_lower in url_lower or _fuzzy_url_match(name, url):
                results.append({
                    'url': url,
                    'source': 'wayback_extract',
                    'title': f'Wayback: {serial}',
                    'file': os.path.basename(url),
                })
        
        # Links do archive.org
        elif 'archive.org/download/' in url_lower:
            results.append({
                'url': url,
                'source': 'wayback_archive',
                'title': f'Wayback->Archive: {serial}',
                'file': os.path.basename(url),
            })
        
        # Links de dl.coolrom.com
        elif 'dl.coolrom.com' in url_lower:
            results.append({
                'url': url,
                'source': 'wayback_coolrom',
                'title': f'Wayback/CoolROM: {serial}',
                'file': os.path.basename(url),
            })
    
    return results

def _fuzzy_url_match(name, url):
    """Verifica se o nome aparece parcialmente na URL."""
    if not name:
        return False
    url_lower = url.lower()
    words = re.split(r'[\s\-_]+', name.lower())
    significant = [w for w in words if len(w) > 2 and w not in {'the', 'and', 'for', 'psx', 'ps1'}]
    if not significant:
        return False
    # Pelo menos 2 palavras significativas na URL
    matches = sum(1 for w in significant if w in url_lower)
    return matches >= min(2, len(significant))

def search_duckduckgo_variations(query, serial, max_results=5):
    """
    Busca no DuckDuckGo Lite com variacoes de termos.
    Diferente da busca google atual, usa DuckDuckGo com operadores especificos.
    """
    results = []
    
    try:
        url = 'https://lite.duckduckgo.com/lite/'
        data = {
            'q': f'{query} psx rom download',
            'kl': 'us-en',
        }
        r = requests.post(url, data=data, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        if r.status_code == 200:
            # DuckDuckGo Lite tem links em <a class="result-link" href="...">
            for match in re.finditer(r'href="(https?://[^"]+)"', r.text, re.I):
                u = match.group(1)
                u_lower = u.lower()
                
                # Filtrar URLs de sites de ROMs conhecidos
                if any(site in u_lower for site in KNOWN_ROM_SITES):
                    if any(ext in u_lower for ext in ['.bin', '.iso', '.img', '.chd', '.7z', '.zip']):
                        results.append({
                            'url': u,
                            'source': 'ddg_variation',
                            'title': f'DDG: {serial}',
                            'file': os.path.basename(u),
                        })
                    elif 'archive.org' in u and '/details/' in u:
                        m = re.search(r'/details/([a-zA-Z0-9_\-\.]+)', u)
                        if m:
                            identifier = m.group(1)
                            files = _get_archive_files(identifier)
                            for f in files:
                                if any(f.lower().endswith(ext) for ext in ROM_EXTS):
                                    dl_url = f'https://archive.org/download/{identifier}/{quote(f)}'
                                    results.append({
                                        'url': dl_url,
                                        'source': 'ddg_archive',
                                        'title': f'DDG->Archive: {identifier}',
                                        'file': f,
                                        'identifier': identifier,
                                    })
                                    if len(results) >= max_results:
                                        return results
    except Exception as e:
        _log(f"  ddg erro: {e}")
    
    return results

def search_archive_org_filename(serial, name, max_results=5):
    """
    Busca no archive.org por NOME DE ARQUIVO que contenha o serial.
    Usa a API de busca por arquivo (filename search).
    """
    if not _archive_available():
        return []
    results = []
    
    # Variacoes de como o serial pode aparecer no nome do arquivo
    serial_variations = [
        serial,                          # SLPS-01224
        serial.replace('-', ''),         # SLPS01224
        serial.replace('-', '_'),        # SLPS_01224
        serial.replace('-', ' '),        # SLPS 01224
        serial.lower(),                  # slps-01224
    ]
    
    for sv in serial_variations:
        if not _archive_available():
            break
        try:
            # Buscar por nome de arquivo
            url = 'https://archive.org/advancedsearch.php'
            params = {
                'q': f'filename:({quote(sv)}) AND mediatype:(software)',
                'fl[]': ['identifier', 'title'],
                'rows': str(max_results),
                'output': 'json',
            }
            r = requests.get(url, params=params, timeout=ARCHIVE_TIMEOUT, headers=HEADERS, proxies=TOR_PROXY)
            if r.status_code == 200:
                _archive_success()
                data = r.json()
                docs = data.get('response', {}).get('docs', [])
                for doc in docs:
                    identifier = doc.get('identifier', '')
                    title = doc.get('title', '')
                    if not identifier:
                        continue
                    files = _get_archive_files(identifier)
                    for f in files:
                        if sv.lower() in f.lower() and any(f.lower().endswith(ext) for ext in ROM_EXTS):
                            dl_url = f'https://archive.org/download/{identifier}/{quote(f)}'
                            results.append({
                                'url': dl_url,
                                'source': 'archive_filename',
                                'title': title,
                                'file': f,
                                'identifier': identifier,
                            })
                            if len(results) >= max_results:
                                return results
        except Exception as e:
            _log(f"  archive_filename erro: {e}")
            _archive_failed()
            break  # Parar se archive.org falhou
    
    return results

def search_direct_sites_by_name(serial, name, max_results=5):
    """
    Busca DIRETA em sites de ROMs usando o NOME RESOLVIDO.
    Esta e a grande vantagem do deep search: o sistema atual nao tem nomes
    na fila (estao vazios), entao nao consegue buscar por nome em sites
    que dependem de nome. O deep search resolve o nome primeiro.
    
    Sites tentados:
    - romspedia.com (busca por nome, URL pattern previsivel)
    - retromania.gg (busca por nome)
    - romsfun.com (busca por nome)
    - blueroms.ws (busca por nome)
    - hexrom.com (busca por nome)
    """
    results = []
    if not name or len(name) < 3:
        return results
    
    # Gerar slug do nome (lowercase, hifens)
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower()).strip('-')
    slug = re.sub(r'-+', '-', slug)
    
    sites_to_try = [
        # (nome, url_pattern, extrai_links_de)
        ('romspedia', f'https://romspedia.com/roms/playstation-1/{slug}-{serial.lower()}',
         'direct'),
        ('romspedia_search', f'https://romspedia.com/roms/playstation-1?q={quote(name)}',
         'html'),
        ('retromania', f'https://retromania.gg/roms/playstation?q={quote(name)}',
         'html'),
        ('romsfun', f'https://romsfun.com/?s={quote(name)}',
         'html'),
        ('blueroms', f'https://blueroms.ws/ps1?search={quote(name)}',
         'html'),
        ('hexrom', f'https://hexrom.com/?s={quote(name)}',
         'html'),
    ]
    
    for site_name, url, extract_type in sites_to_try:
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS, allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 500:
                # Extrair links de download da pagina
                found = _extract_download_links_from_page(r.text, serial, name, site_name)
                if found:
                    results.extend(found)
                    _log(f"    {site_name}: {len(found)} links encontrados")
                    if len(results) >= max_results:
                        return results
        except Exception as e:
            _log(f"    {site_name} erro: {e}")
    
    return results

def _extract_download_links_from_page(html, serial, name, site_name):
    """Extrai links de download de uma pagina de site de ROMs."""
    results = []
    serial_lower = serial.lower()
    serial_nohyphen = serial.replace('-', '').lower()
    
    # Procurar por links que parecem ser de download
    for match in re.finditer(r'href="(https?://[^"]+)"', html, re.I):
        url = match.group(1)
        url_lower = url.lower()
        
        # Links diretos de ROM
        if any(ext in url_lower for ext in ['.bin', '.iso', '.img', '.chd', '.7z', '.zip', '.ecm']):
            # Verificar se o serial ou nome esta na URL
            if serial_lower in url_lower or serial_nohyphen in url_lower or _fuzzy_url_match(name, url):
                results.append({
                    'url': url,
                    'source': f'direct_{site_name}',
                    'title': f'{site_name}: {serial}',
                    'file': os.path.basename(url),
                })
        
        # Links de download de sites conhecidos
        elif any(dl in url_lower for dl in ['dl.coolrom.com', '/download/', 'files.']):
            if _fuzzy_url_match(name, url) or serial_lower in url_lower:
                results.append({
                    'url': url,
                    'source': f'direct_{site_name}',
                    'title': f'{site_name}: {serial}',
                    'file': os.path.basename(url),
                })
    
    # Procurar por archive.org identifiers na pagina
    for match in re.finditer(r'archive\.org/(?:download|details)/([a-zA-Z0-9_\-\.]+)', html, re.I):
        identifier = match.group(1)
        if serial_lower in identifier.lower() or serial_nohyphen in identifier.lower():
            files = _get_archive_files(identifier)
            for f in files:
                if any(f.lower().endswith(ext) for ext in ROM_EXTS):
                    dl_url = f'https://archive.org/download/{identifier}/{quote(f)}'
                    results.append({
                        'url': dl_url,
                        'source': f'direct_{site_name}_archive',
                        'title': f'{site_name}->Archive: {identifier}',
                        'file': f,
                        'identifier': identifier,
                    })
    
    return results

def search_bing_general(query, serial, name, max_results=5):
    """
    Busca geral no Bing (sem site: especifico).
    Usa variacoes de termos e extrai links de ROMs dos resultados.
    """
    results = []
    full_query = f'{query} psx rom download'
    
    try:
        url = 'https://www.bing.com/search'
        params = {
            'q': full_query,
            'count': '20',
            'setlang': 'en-US',
        }
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        if r.status_code == 200:
            urls_found = set()
            
            # Extrair URLs de resultados do Bing
            for match in re.finditer(r'href="(https?://[^"]+)"', r.text, re.I):
                u = match.group(1)
                if 'bing.com' in u or 'microsoft.com' in u:
                    continue
                if any(site in u.lower() for site in KNOWN_ROM_SITES):
                    urls_found.add(u)
            
            # Filtrar URLs uteis
            for u in urls_found:
                u_lower = u.lower()
                if any(ext in u_lower for ext in ['.bin', '.iso', '.img', '.chd', '.7z', '.zip']):
                    results.append({
                        'url': u,
                        'source': 'bing_general',
                        'title': f'Bing: {serial}',
                        'file': os.path.basename(u),
                    })
                elif 'archive.org' in u and '/details/' in u:
                    m = re.search(r'/details/([a-zA-Z0-9_\-\.]+)', u)
                    if m:
                        identifier = m.group(1)
                        files = _get_archive_files(identifier)
                        for f in files:
                            if any(f.lower().endswith(ext) for ext in ROM_EXTS):
                                dl_url = f'https://archive.org/download/{identifier}/{quote(f)}'
                                results.append({
                                    'url': dl_url,
                                    'source': 'bing_general_archive',
                                    'title': f'Bing->Archive: {identifier}',
                                    'file': f,
                                    'identifier': identifier,
                                })
                                if len(results) >= max_results:
                                    return results
                else:
                    # Pagina de site de ROM - buscar link de download nela
                    try:
                        r2 = requests.get(u, timeout=REQUEST_TIMEOUT, headers=HEADERS)
                        if r2.status_code == 200:
                            found = _extract_download_links_from_page(r2.text, serial, name, 'bing_page')
                            results.extend(found)
                            if len(results) >= max_results:
                                return results
                    except:
                        pass
    except Exception as e:
        _log(f"  bing_general erro: {e}")
    
    return results

# ============================================================
# ORQUESTRADOR PRINCIPAL
# ============================================================

def search_deep(serial, name='', timeout_per_source=20):
    """
    Funcao principal de deep search.
    Combina todas as fontes nao exploradas com variacoes de termos.
    As camadas rodam EM PARALELO para maximizar velocidade.
    
    Retorna lista de resultados com URLs de download.
    """
    # Verificar cache
    cache_key = f'{serial}:{name}'
    cached = _cache_get(cache_key)
    if cached is not None:
        _log(f"[{serial}] cache hit: {len(cached)} resultados")
        return cached
    
    # Resolver nome se nao fornecido
    if not name:
        name = resolve_name(serial)
        _log(f"[{serial}] nome resolvido: '{name}'")
    
    # Gerar variacoes de termos
    variations = generate_term_variations(serial, name)
    _log(f"[{serial}] {len(variations)} variacoes: {variations[:5]}...")
    
    all_results = []
    
    # Definir tarefas paralelas (cada uma retorna lista de resultados)
    tasks = {}
    
    # CAMADA PRIORITARIA: Busca direta em sites de ROMs por NOME RESOLVIDO
    # Esta e a grande vantagem: o sistema atual nao tem nomes, o deep search resolve
    if name:
        tasks['direct_sites'] = lambda: search_direct_sites_by_name(serial, name)
    
    # CAMADA PRIORITARIA: Bing geral (extrai links de ROMs de resultados)
    if variations:
        v0 = variations[0]
        tasks['bing_general'] = lambda: search_bing_general(v0, serial, name)
    
    # Tarefa: GitHub (sempre roda - rapido)
    tasks['github'] = lambda: search_github(serial, name)
    
    # Tarefa: Bing com site: especifico
    if variations:
        v0 = variations[0]
        tasks['bing_reddit'] = lambda: search_bing_site(v0, 'reddit.com', serial)
    
    # Tarefa: DuckDuckGo (sempre roda)
    if variations:
        v0 = variations[0]
        tasks['ddg'] = lambda: search_duckduckgo_variations(v0, serial)
    
    # Tarefa: Wayback Machine
    tasks['wayback'] = lambda: search_wayback_machine(serial, name)
    
    # Tarefas: Archive.org (so roda se archive.org estiver disponivel)
    if _archive_available():
        tasks['archive_filename'] = lambda: search_archive_org_filename(serial, name)
        if name and variations:
            v0 = variations[0]
            tasks['archive_collections'] = lambda: search_archive_org_collections(v0, serial)
    
    # Executar todas as tarefas em paralelo
    _log(f"[{serial}] Executando {len(tasks)} camadas em paralelo: {list(tasks.keys())}")
    
    with ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as executor:
        futures = {
            executor.submit(fn): name_task
            for name_task, fn in tasks.items()
        }
        
        try:
            for future in as_completed(futures, timeout=timeout_per_source + 5):
                task_name = futures[future]
                try:
                    results = future.result(timeout=2)
                    if results:
                        all_results.extend(results)
                        _log(f"[{serial}] {task_name}: {len(results)} resultados")
                except Exception as e:
                    _log(f"[{serial}] {task_name} erro: {e}")
                    if 'archive' in task_name:
                        _archive_failed()
        except TimeoutError:
            # Algumas tarefas nao completaram a tempo - pegar as que completaram
            _log(f"[{serial}] timeout em algumas camadas")
            for future, task_name in futures.items():
                if future.done() and not future.cancelled():
                    try:
                        results = future.result(timeout=0.1)
                        if results:
                            all_results.extend(results)
                    except:
                        pass
            # Marcar archive.org como falhou se ainda estava rodando
            for future, task_name in futures.items():
                if not future.done() and 'archive' in task_name:
                    _archive_failed()
    
    # Deduplicar por URL
    seen_urls = set()
    unique = []
    for r in all_results:
        if r['url'] not in seen_urls:
            seen_urls.add(r['url'])
            unique.append(r)
    
    _log(f"[{serial}] TOTAL: {len(unique)} resultados unicos")
    
    # Salvar no cache
    _cache_set(cache_key, unique)
    
    return unique

# ============================================================
# TESTE STANDALONE
# ============================================================

if __name__ == '__main__':
    import sys
    
    # Carregar pendentes
    with open(os.path.join(STATE_DIR, 'queue.json'), 'r', encoding='utf-8') as f:
        q = json.load(f)
    queue = q.get('queue', [])
    
    print(f"=== DEEP SEARCH TEST ===")
    print(f"Pendentes: {len(queue)}")
    print()
    
    for item in queue:
        serial = item.get('serial', '')
        name = item.get('name', '')
        
        if serial.startswith(('NOSERIAL', 'BREW')):
            print(f"\n[{serial}] Pulando (homebrew/noserial)")
            continue
        
        print(f"\n[{serial}] (name='{name}')")
        results = search_deep(serial, name)
        
        if results:
            print(f"  ENCONTRADO! {len(results)} resultados:")
            for r in results:
                print(f"    URL: {r['url'][:100]}")
                print(f"    Source: {r['source']} | File: {r.get('file','')}")
        else:
            print(f"  Nao encontrado")
