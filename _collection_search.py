"""
Busca ROMs em collections específicas do archive.org listando arquivos diretamente.
Estratégia: muitas collections redump têm os arquivos nomeados por serial.
Ex: Redump.orgSonyPlayStation-NTSC-U-S contém "SLUS-01527.zip"
"""
import sys, os, time, json, re
from urllib.parse import quote, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r"D:\roms\library\roms\_importre_state"
CACHE_PATH = os.path.join(STATE_DIR, "collection_file_index.json")

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')

# Collections conhecidas — listar arquivos de cada uma
COLLECTIONS = [
    # Redump por região
    "Redump.orgSonyPlayStation-NTSC-U-A",
    "Redump.orgSonyPlayStation-NTSC-U-B",
    "Redump.orgSonyPlayStation-NTSC-U-C",
    "Redump.orgSonyPlayStation-NTSC-U-D",
    "Redump.orgSonyPlayStation-NTSC-U-E",
    "Redump.orgSonyPlayStation-NTSC-U-F",
    "Redump.orgSonyPlayStation-NTSC-U-G",
    "Redump.orgSonyPlayStation-NTSC-U-H",
    "Redump.orgSonyPlayStation-NTSC-U-I",
    "Redump.orgSonyPlayStation-NTSC-U-J",
    "Redump.orgSonyPlayStation-NTSC-U-K",
    "Redump.orgSonyPlayStation-NTSC-U-L",
    "Redump.orgSonyPlayStation-NTSC-U-M",
    "Redump.orgSonyPlayStation-NTSC-U-N",
    "Redump.orgSonyPlayStation-NTSC-U-O",
    "Redump.orgSonyPlayStation-NTSC-U-P",
    "Redump.orgSonyPlayStation-NTSC-U-Q",
    "Redump.orgSonyPlayStation-NTSC-U-R",
    "Redump.orgSonyPlayStation-NTSC-U-S",
    "Redump.orgSonyPlayStation-NTSC-U-T",
    "Redump.orgSonyPlayStation-NTSC-U-U",
    "Redump.orgSonyPlayStation-NTSC-U-V",
    "Redump.orgSonyPlayStation-NTSC-U-W",
    "Redump.orgSonyPlayStation-NTSC-U-X",
    "Redump.orgSonyPlayStation-NTSC-U-Y",
    "Redump.orgSonyPlayStation-NTSC-U-Z",
    # Redump PAL
    "Redump.orgSonyPlayStation-PAL-A",
    "Redump.orgSonyPlayStation-PAL-B",
    "Redump.orgSonyPlayStation-PAL-C",
    "Redump.orgSonyPlayStation-PAL-D",
    "Redump.orgSonyPlayStation-PAL-E",
    "Redump.orgSonyPlayStation-PAL-F",
    "Redump.orgSonyPlayStation-PAL-G",
    "Redump.orgSonyPlayStation-PAL-H",
    "Redump.orgSonyPlayStation-PAL-I",
    "Redump.orgSonyPlayStation-PAL-J",
    "Redump.orgSonyPlayStation-PAL-K",
    "Redump.orgSonyPlayStation-PAL-L",
    "Redump.orgSonyPlayStation-PAL-M",
    "Redump.orgSonyPlayStation-PAL-N",
    "Redump.orgSonyPlayStation-PAL-O",
    "Redump.orgSonyPlayStation-PAL-P",
    "Redump.orgSonyPlayStation-PAL-Q",
    "Redump.orgSonyPlayStation-PAL-R",
    "Redump.orgSonyPlayStation-PAL-S",
    "Redump.orgSonyPlayStation-PAL-T",
    "Redump.orgSonyPlayStation-PAL-U",
    "Redump.orgSonyPlayStation-PAL-V",
    "Redump.orgSonyPlayStation-PAL-W",
    "Redump.orgSonyPlayStation-PAL-X",
    "Redump.orgSonyPlayStation-PAL-Y",
    "Redump.orgSonyPlayStation-PAL-Z",
    # Redump Japan
    "Redump.orgSonyPlayStation-NTSC-J-A",
    "Redump.orgSonyPlayStation-NTSC-J-B",
    "Redump.orgSonyPlayStation-NTSC-J-C",
    "Redump.orgSonyPlayStation-NTSC-J-D",
    "Redump.orgSonyPlayStation-NTSC-J-E",
    "Redump.orgSonyPlayStation-NTSC-J-F",
    "Redump.orgSonyPlayStation-NTSC-J-G",
    "Redump.orgSonyPlayStation-NTSC-J-H",
    "Redump.orgSonyPlayStation-NTSC-J-I",
    "Redump.orgSonyPlayStation-NTSC-J-J",
    "Redump.orgSonyPlayStation-NTSC-J-K",
    "Redump.orgSonyPlayStation-NTSC-J-L",
    "Redump.orgSonyPlayStation-NTSC-J-M",
    "Redump.orgSonyPlayStation-NTSC-J-N",
    "Redump.orgSonyPlayStation-NTSC-J-O",
    "Redump.orgSonyPlayStation-NTSC-J-P",
    "Redump.orgSonyPlayStation-NTSC-J-Q",
    "Redump.orgSonyPlayStation-NTSC-J-R",
    "Redump.orgSonyPlayStation-NTSC-J-S",
    "Redump.orgSonyPlayStation-NTSC-J-T",
    "Redump.orgSonyPlayStation-NTSC-J-U",
    "Redump.orgSonyPlayStation-NTSC-J-V",
    "Redump.orgSonyPlayStation-NTSC-J-W",
    "Redump.orgSonyPlayStation-NTSC-J-X",
    "Redump.orgSonyPlayStation-NTSC-J-Y",
    "Redump.orgSonyPlayStation-NTSC-J-Z",
    # Outras collections
    "redump_psx",
    "psx-roms-archive",
    "CuratedPSXRedumpCHDs",
    "Redump_PSX_2021_06_04_A_C",
    "Redump_PSX_2021_06_04_D_F",
    "Redump_PSX_2021_06_04_G_I",
    "Redump_PSX_2021_06_04_J_L",
    "Redump_PSX_2021_06_04_M_O",
    "Redump_PSX_2021_06_04_P_R",
    "Redump_PSX_2021_06_04_S_U",
    "Redump_PSX_2021_06_04_V_X",
    "Redump_PSX_2021_06_04_Y_Z",
]


def list_collection_files(identifier):
    """Lista arquivos de um item/collection do archive.org via API metadata."""
    url = f"http://archive.org/metadata/{identifier}"
    try:
        r = s.get(url, timeout=(5, 20))
        if r.status_code == 200:
            data = r.json()
            files = data.get('files', [])
            return [(f.get('name', ''), f.get('size', '0')) for f in files]
    except:
        pass
    return []


def build_index():
    """Constrói índice de todos os arquivos ROM em todas as collections."""
    print(f"Construindo índice de {len(COLLECTIONS)} collections...", flush=True)
    index = {}  # serial -> [(collection, filename, size)]

    def fetch_collection(coll):
        files = list_collection_files(coll)
        roms = []
        for fname, size in files:
            fname_lower = fname.lower()
            if not any(fname_lower.endswith(ext) for ext in ROM_EXTS):
                continue
            # Extrair serial do nome do arquivo
            # Padrões comuns: SLUS-01234.zip, SLES-00567.bin, SLPS-00890.7z
            match = re.search(r'(S[LC][EUP]S?-\d{4,5})', fname_upper := fname.upper())
            if match:
                serial = match.group(1)
                roms.append((serial, coll, fname, size))
        return coll, roms

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_collection, c): c for c in COLLECTIONS}
        for f in as_completed(futures):
            coll = futures[f]
            try:
                _, roms = f.result()
                for serial, coll, fname, size in roms:
                    if serial not in index:
                        index[serial] = []
                    index[serial].append((coll, fname, size))
                if roms:
                    print(f"  {coll}: {len(roms)} ROMs", flush=True)
            except Exception as e:
                print(f"  {coll}: erro {e}", flush=True)

    # Salvar índice
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\nÍndice: {len(index)} seriais únicos em {len(COLLECTIONS)} collections", flush=True)
    return index


def load_index():
    """Carrega índice do cache ou constrói se não existir."""
    if os.path.exists(CACHE_PATH):
        mtime = os.path.getmtime(CACHE_PATH)
        if time.time() - mtime < 86400:  # < 24h
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    return build_index()


def find_rom(index, serial):
    """Procura um serial no índice. Retorna lista de (collection, filename, size)."""
    return index.get(serial.upper(), [])


def build_download_url(collection, filename):
    """Constrói URL de download direto."""
    return f"http://archive.org/download/{collection}/{quote(filename, safe='/')}"


def main():
    print("=" * 60, flush=True)
    print("COLLECTION SEARCH — busca em collections redump", flush=True)
    print("=" * 60, flush=True)

    # Construir/carregar índice
    index = load_index()
    print(f"Índice: {len(index)} seriais\n", flush=True)

    # Carregar pendentes
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

    # Coletar todos os seriais únicos (pending + failed)
    seen = set()
    to_search = []
    for item in pending:
        if isinstance(item, dict):
            sr = item.get('serial', '')
            if sr and sr not in seen and sr not in completed:
                seen.add(sr)
                to_search.append(item)

    # Adicionar failed também
    for sr, info in failed.items():
        if sr not in seen:
            seen.add(sr)
            to_search.append({'serial': sr, 'name': info.get('name', '')})

    print(f"Buscando {len(to_search)} ROMs no índice...\n", flush=True)

    found = []
    not_found = []
    for item in to_search:
        serial = item.get('serial', '')
        name = item.get('name', '')
        matches = find_rom(index, serial)
        if matches:
            coll, fname, size = matches[0]
            url = build_download_url(coll, fname)
            size_mb = int(size) / 1024 / 1024 if size.isdigit() else 0
            print(f"  {serial}: ENCONTRADO em {coll} ({fname}, {size_mb:.1f}MB)", flush=True)
            found.append({'serial': serial, 'name': name, 'url': url, 'collection': coll, 'filename': fname})
        else:
            print(f"  {serial}: não encontrado ({name[:30]})", flush=True)
            not_found.append(serial)

    print(f"\n=== RESULTADO ===", flush=True)
    print(f"Encontrados: {len(found)}", flush=True)
    print(f"Não encontrados: {len(not_found)}", flush=True)

    # Salvar resultados
    results_path = os.path.join(STATE_DIR, "collection_search_results.json")
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({'found': found, 'not_found': not_found}, f, ensure_ascii=False, indent=2)
    print(f"Resultados salvos em: {results_path}", flush=True)


if __name__ == '__main__':
    main()
