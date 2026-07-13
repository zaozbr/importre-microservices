"""
Wrapper sequencial para Tor:
1. Busca ROMs UM POR VEZ via Tor (archive.org) e outros sites
2. Acumula URLs de download encontradas
3. Quando atinge 40 resultados positivos (ou esgota a fila), inicia downloads
4. Downloads tambem sequenciais (1 por vez) para nao sobrecarregar Tor
"""
import sys, os, time, json, socket, traceback
sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
socket.setdefaulttimeout(120)

# Sem proxy global — archive_request usa Tor internamente
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('NO_PROXY', None)

import importre
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(r"D:\roms\library\roms\_importre_state\importre.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("seq_wrapper")

STATE_DIR = importre.STATE_DIR
QUEUE_PATH = importre.QUEUE_PATH
DOWNLOADS_DIR = importre.DOWNLOADS_TMP

TARGET_RESULTS = 40

# Ordem de prioridade de sites
SITE_ORDER = [
    'archive_org', 'archive_org_jp',     # via Tor
    'coolrom', 'hexrom',                  # direto
    'psxdatacenter_jp', 'retrostic_jp',   # direto
    'romulation', 'retroiso',             # direto
    'homebrew',                           # direto
    'romspedia', 'romsretro', 'romsgames',
    'consoleroms', 'retromania', 'romsdl',
    'romspure', 'oldiesnest', 'retrostic',
    'google',                             # fallback
]


def load_queue():
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_queue(q):
    with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(q, f, ensure_ascii=False, indent=2)

def build_search_funcs(serial, name):
    """Construir dict de funcoes de busca como no importre.py (FakeNav)."""
    short_query = serial  # busca por serial

    # FakeNav: instancia fake para chamar metodos do SiteNavigator sem Playwright
    class FakeNav:
        pass
    fake = FakeNav()
    SN = importre.SiteNavigator
    for method_name in ['search_coolrom', 'search_homebrew', 'search_archive_org',
                        'search_archive_org_jp', 'search_retrostic', 'search_retrostic_jp',
                        'search_romsdl', 'search_romspedia', 'search_retroiso',
                        'search_retromania', 'search_romsgames', 'search_hexrom',
                        'search_consoleroms', 'search_romulation', 'search_romspure',
                        'search_oldiesnest', 'search_google', 'search_psxdatacenter_jp',
                        'search_blueroms', 'search_romsretro']:
        if hasattr(SN, method_name):
            fake.__dict__[method_name] = getattr(SN, method_name).__get__(fake)

    return {
        "coolrom": lambda: fake.search_coolrom(short_query, serial, name),
        "blueroms": lambda: fake.search_blueroms(short_query, serial, name),
        "romsretro": lambda: fake.search_romsretro(short_query, serial, name),
        "retrostic": lambda: fake.search_retrostic(short_query, serial, name),
        "romsdl": lambda: fake.search_romsdl(short_query, serial, name),
        "archive_org": lambda: fake.search_archive_org(short_query, serial, name),
        "archive_org_jp": lambda: fake.search_archive_org_jp(short_query, serial, name),
        "psxdatacenter_jp": lambda: fake.search_psxdatacenter_jp(short_query, serial, name),
        "retrostic_jp": lambda: fake.search_retrostic_jp(short_query, serial, name),
        "romspedia": lambda: fake.search_romspedia(short_query, serial, name),
        "retroiso": lambda: fake.search_retroiso(short_query, serial, name),
        "retromania": lambda: fake.search_retromania(short_query, serial, name),
        "romsgames": lambda: fake.search_romsgames(short_query, serial, name),
        "hexrom": lambda: fake.search_hexrom(short_query, serial, name),
        "consoleroms": lambda: fake.search_consoleroms(short_query, serial, name),
        "romulation": lambda: fake.search_romulation(short_query, serial, name),
        "romspure": lambda: fake.search_romspure(short_query, serial, name),
        "oldiesnest": lambda: fake.search_oldiesnest(short_query, serial, name),
        "google": lambda: fake.search_google(short_query, serial, name),
        "homebrew": lambda: fake.search_homebrew(name, serial, name),
    }


def search_one_serial(serial, name, sites, blacklist):
    """Busca UM ROM sequencialmente em todos os sites. Retorna (site_key, result, detail) ou (None, None, None)."""
    search_funcs = build_search_funcs(serial, name)

    for site_key in SITE_ORDER:
        if site_key not in sites:
            continue
        site = sites[site_key]
        if not site.get('enabled', True):
            continue
        if site_key in blacklist.get('sites', []):
            continue

        search_fn = search_funcs.get(site_key)
        if not search_fn:
            continue

        t0 = time.time()
        log.info(f"  {serial}: tentando {site_key}...")
        try:
            result, detail = search_fn()
        except Exception as e:
            log.debug(f"  {serial}: {site_key} erro: {str(e)[:100]}")
            result, detail = None, str(e)

        dt = time.time() - t0
        if result:
            log.info(f"  {serial}: SUCESSO em {site_key} ({dt:.1f}s)")
            return site_key, result, detail
        else:
            log.info(f"  {serial}: {site_key} fail ({dt:.1f}s)")

    return None, None, None


def download_one_serial(serial, url, site_key):
    """Baixa UM ROM. Usa archive_request (Tor) se archive.org, senao direto."""
    # FakeNav para download_direct_url
    class FakeNav:
        pass
    fake = FakeNav()
    SN = importre.SiteNavigator
    fake.download_direct_url = SN.download_direct_url.__get__(fake)
    try:
        dest, msg = fake.download_direct_url(url, serial)
        return dest, msg
    except Exception as e:
        return None, f"erro: {str(e)[:150]}"


def resolve_archive_item_to_url(identifier, serial):
    """Dado um archive_item (identifier), busca a metadata para encontrar o arquivo
    que corresponde ao serial e retorna a URL direta de download."""
    from urllib.parse import quote

    # Buscar metadata do item
    meta_url = f"http://archive.org/metadata/{identifier}"
    try:
        resp = importre.archive_request("get", meta_url, timeout=(10, 30),
                                         headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception as e:
        log.warning(f"resolve_archive_item: erro metadata {identifier}: {e}")
        return None

    files = data.get("files", [])
    if not files:
        return None

    # Procurar arquivo que corresponde ao serial
    serial_lower = serial.lower().replace("-", "")
    serial_underscore = serial.lower().replace("-", "_")

    # Prioridade: arquivo com serial no nome, extensao de ROM
    rom_exts = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd')

    candidates = []
    for f in files:
        fname = f.get("name", "")
        fname_lower = fname.lower()
        # Pular arquivos nao-ROM
        if not any(fname_lower.endswith(ext) for ext in rom_exts):
            continue
        # Score por correspondencia
        score = 0
        if serial_lower in fname_lower.replace("-", "").replace("_", "").replace(" ", ""):
            score = 100
        elif serial_underscore in fname_lower:
            score = 80
        elif serial_lower in fname_lower:
            score = 60
        # Preferir .zip/.7z/.chd (pacote completo) ou .bin+.cue
        if fname_lower.endswith(('.zip', '.7z', '.chd')):
            score += 10
        candidates.append((score, fname))

    if not candidates:
        # Fallback: primeiro arquivo ROM
        for f in files:
            fname = f.get("name", "")
            if any(fname.lower().endswith(ext) for ext in rom_exts):
                candidates.append((0, fname))
                break

    if not candidates:
        return None

    # Ordenar por score (maior primeiro)
    candidates.sort(key=lambda x: -x[0])
    best_fname = candidates[0][1]
    encoded_fname = quote(best_fname, safe="/")
    return f"http://archive.org/download/{identifier}/{encoded_fname}"


def main():
    print("[SEQ] Iniciando wrapper sequencial Tor...", flush=True)

    # Inicializar
    importre.init_queue()
    print("[SEQ] init_queue done", flush=True)

    # Limpar itens presos
    try:
        importre.cleanup_stale_items(max_age_seconds=60)
    except Exception:
        pass
    try:
        importre.clear_control()
    except Exception:
        pass
    print("[SEQ] cleanup done", flush=True)

    # Carregar sites e blacklist
    sites = importre.load_sites()
    blacklist = importre.load_blacklist()
    print(f"[SEQ] {len(sites)} sites, {len(blacklist.get('sites',[]))} blacklistados", flush=True)

    round_num = 0
    while True:
        q = load_queue()
        pending = q.get('queue', [])
        completed = q.get('completed', {})
        failed = q.get('failed', {})
        in_progress = q.get('in_progress', {})

        # Filtrar pendentes reais
        to_search = []
        for item in pending:
            if isinstance(item, dict):
                s = item.get('serial', '')
                if s and s not in completed and s not in failed and s not in in_progress:
                    to_search.append(item)

        if not to_search:
            # Verificar se ha falhos para retry
            if failed:
                print(f"[SEQ] Fila vazia mas {len(failed)} falhos. Fazendo retry...", flush=True)
                q = load_queue()
                fl = q.get('failed', {})
                if not isinstance(fl, dict):
                    fl = {}
                queue = q.get('queue', [])
                for s, info in fl.items():
                    queue.append({'serial': s, 'name': info.get('name', '')})
                q['queue'] = queue
                q['failed'] = {}
                save_queue(q)
                continue
            print("[SEQ] Fila esgotada! Encerrando.", flush=True)
            break

        round_num += 1
        print(f"\n[SEQ] === RODADA {round_num}: {len(to_search)} pendentes ===", flush=True)

        # FASE 1: BUSCAS SEQUENCIAIS
        found_urls = {}

        for i, item in enumerate(to_search):
            serial = item.get('serial', '')
            name = item.get('name', '')
            print(f"\n[SEQ] [{i+1}/{len(to_search)}] Buscando {serial} ({name[:30]})...", flush=True)

            # Marcar como in_progress
            q = load_queue()
            ip = q.get('in_progress', {})
            if not isinstance(ip, dict):
                ip = {}
            item['_phase'] = 'searching'
            item['_started_at'] = time.time()
            ip[serial] = item
            q['in_progress'] = ip
            save_queue(q)

            site_key, result, detail = search_one_serial(serial, name, sites, blacklist)

            if result:
                found_urls[serial] = {
                    'site_key': site_key,
                    'result': result,
                    'detail': detail,
                    'item': item,
                }
                print(f"[SEQ] {serial}: ENCONTRADO em {site_key} ({len(found_urls)} acumulados)", flush=True)

                if len(found_urls) >= TARGET_RESULTS:
                    print(f"\n[SEQ] *** {TARGET_RESULTS} resultados! Iniciando downloads... ***", flush=True)
                    break
            else:
                # Marcar como falho
                q = load_queue()
                ip = q.get('in_progress', {})
                if not isinstance(ip, dict):
                    ip = {}
                ip.pop(serial, None)
                fl = q.get('failed', {})
                if not isinstance(fl, dict):
                    fl = {}
                fl[serial] = {'reason': 'nao encontrado', 'failed_at': time.time(), 'name': name}
                q['in_progress'] = ip
                q['failed'] = fl
                save_queue(q)
                print(f"[SEQ] {serial}: FALHOU busca", flush=True)

        # FASE 2: DOWNLOADS SEQUENCIAIS
        if not found_urls:
            print(f"\n[SEQ] Nenhuma URL encontrada. Continuando...", flush=True)
            continue

        print(f"\n[SEQ] === DOWNLOADS: {len(found_urls)} ROMs ===", flush=True)

        for serial, info in found_urls.items():
            site_key = info['site_key']
            result = info['result']
            detail = info.get('detail', '')
            item = info['item']

            # O resultado das funcoes de busca e uma TUPLA: (tipo, valor)
            # Tipos possiveis:
            #   ("direct_url", "http://archive.org/download/IDENT/FILE")
            #   ("archive_item", "IDENTIFIER")  — precisa buscar metadata p/ achar arquivo
            #   ("url", "http://...")           — URL direta de outros sites
            # Outros sites podem retornar string direta ou dict.
            url = None
            archive_item = None

            if isinstance(result, tuple) and len(result) == 2:
                rtype, rval = result
                if rtype == "direct_url":
                    url = rval
                elif rtype == "archive_item":
                    archive_item = rval
                elif rtype == "url":
                    url = rval
                else:
                    # Tipo desconhecido — tentar como URL
                    url = rval if isinstance(rval, str) else None
            elif isinstance(result, dict):
                url = result.get('direct_url') or result.get('url')
                archive_item = result.get('archive_item')
            elif isinstance(result, str):
                url = result

            # Se temos archive_item mas sem URL, buscar metadata para achar arquivo
            if not url and archive_item:
                print(f"[SEQ] {serial}: archive_item={archive_item}, buscando metadata...", flush=True)
                try:
                    url = resolve_archive_item_to_url(archive_item, serial)
                except Exception as e:
                    print(f"[SEQ] {serial}: erro ao resolver archive_item: {e}", flush=True)
                    url = None

            if not url:
                print(f"[SEQ] {serial}: sem URL, pulando", flush=True)
                q = load_queue()
                ip = q.get('in_progress', {})
                if not isinstance(ip, dict):
                    ip = {}
                ip.pop(serial, None)
                fl = q.get('failed', {})
                if not isinstance(fl, dict):
                    fl = {}
                fl[serial] = {'reason': 'sem URL', 'failed_at': time.time()}
                q['in_progress'] = ip
                q['failed'] = fl
                save_queue(q)
                continue

            print(f"\n[SEQ] Baixando {serial} de {site_key}: {url[:80]}...", flush=True)
            t0 = time.time()
            dest, msg = download_one_serial(serial, url, site_key)
            elapsed = time.time() - t0

            q = load_queue()
            ip = q.get('in_progress', {})
            if not isinstance(ip, dict):
                ip = {}

            if dest:
                ip.pop(serial, None)
                comp = q.get('completed', {})
                if not isinstance(comp, dict):
                    comp = {}
                comp[serial] = {
                    'serial': serial,
                    'name': item.get('name', ''),
                    'site': site_key,
                    'completed_at': time.time(),
                }
                q['in_progress'] = ip
                q['completed'] = comp
                save_queue(q)
                try:
                    size_mb = os.path.getsize(dest) / 1024 / 1024
                except:
                    size_mb = 0
                print(f"[SEQ] {serial}: SUCESSO! {size_mb:.1f}MB em {elapsed:.1f}s", flush=True)
            else:
                ip.pop(serial, None)
                fl = q.get('failed', {})
                if not isinstance(fl, dict):
                    fl = {}
                fl[serial] = {'reason': msg, 'failed_at': time.time()}
                q['in_progress'] = ip
                q['failed'] = fl
                save_queue(q)
                print(f"[SEQ] {serial}: FALHOU download: {msg[:100]}", flush=True)

        # Status
        q = load_queue()
        p = len(q.get('queue', []))
        ip = len(q.get('in_progress', {}))
        d = len(q.get('completed', {}))
        f = len(q.get('failed', {}))
        print(f"\n[SEQ] Status: pending={p} in_prog={ip} done={d} fail={f}", flush=True)

        if p == 0 and ip == 0:
            print("[SEQ] Fila esgotada! Encerrando.", flush=True)
            break

    q = load_queue()
    p = len(q.get('queue', []))
    ip = len(q.get('in_progress', {}))
    d = len(q.get('completed', {}))
    f = len(q.get('failed', {}))
    print(f"\n[SEQ] === FINAL: pending={p} in_prog={ip} done={d} fail={f} ===", flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"[SEQ] ERRO FATAL: {e}", flush=True)
        traceback.print_exc()
