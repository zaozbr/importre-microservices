"""
Índice inteligente de collections do archive.org.
Estratégia: mapear nomes de arquivos (que contêm nomes de jogos) para permitir
busca por nome do jogo, não só por serial.
"""
import sys, os, time, json, re
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r"D:\roms\library\roms\_importre_state"
INDEX_PATH = os.path.join(STATE_DIR, "smart_index.json")

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')

# Todas as collections conhecidas
COLLECTIONS = [
    # NTSC-U por letra
    "Redump.orgSonyPlayStation-NTSC-U-A", "Redump.orgSonyPlayStation-NTSC-U-B",
    "Redump.orgSonyPlayStation-NTSC-U-C", "Redump.orgSonyPlayStation-NTSC-U-D",
    "Redump.orgSonyPlayStation-NTSC-U-E", "Redump.orgSonyPlayStation-NTSC-U-F",
    "Redump.orgSonyPlayStation-NTSC-U-G", "Redump.orgSonyPlayStation-NTSC-U-H",
    "Redump.orgSonyPlayStation-NTSC-U-I", "Redump.orgSonyPlayStation-NTSC-U-J",
    "Redump.orgSonyPlayStation-NTSC-U-K", "Redump.orgSonyPlayStation-NTSC-U-L",
    "Redump.orgSonyPlayStation-NTSC-U-M", "Redump.orgSonyPlayStation-NTSC-U-N",
    "Redump.orgSonyPlayStation-NTSC-U-O", "Redump.orgSonyPlayStation-NTSC-U-P",
    "Redump.orgSonyPlayStation-NTSC-U-Q", "Redump.orgSonyPlayStation-NTSC-U-R",
    "Redump.orgSonyPlayStation-NTSC-U-S", "Redump.orgSonyPlayStation-NTSC-U-T",
    "Redump.orgSonyPlayStation-NTSC-U-U", "Redump.orgSonyPlayStation-NTSC-U-V",
    "Redump.orgSonyPlayStation-NTSC-U-W", "Redump.orgSonyPlayStation-NTSC-U-X",
    "Redump.orgSonyPlayStation-NTSC-U-Y", "Redump.orgSonyPlayStation-NTSC-U-Z",
    # PAL por letra
    "Redump.orgSonyPlayStation-PAL-A", "Redump.orgSonyPlayStation-PAL-B",
    "Redump.orgSonyPlayStation-PAL-C", "Redump.orgSonyPlayStation-PAL-D",
    "Redump.orgSonyPlayStation-PAL-E", "Redump.orgSonyPlayStation-PAL-F",
    "Redump.orgSonyPlayStation-PAL-G", "Redump.orgSonyPlayStation-PAL-H",
    "Redump.orgSonyPlayStation-PAL-I", "Redump.orgSonyPlayStation-PAL-J",
    "Redump.orgSonyPlayStation-PAL-K", "Redump.orgSonyPlayStation-PAL-L",
    "Redump.orgSonyPlayStation-PAL-M", "Redump.orgSonyPlayStation-PAL-N",
    "Redump.orgSonyPlayStation-PAL-O", "Redump.orgSonyPlayStation-PAL-P",
    "Redump.orgSonyPlayStation-PAL-Q", "Redump.orgSonyPlayStation-PAL-R",
    "Redump.orgSonyPlayStation-PAL-S", "Redump.orgSonyPlayStation-PAL-T",
    "Redump.orgSonyPlayStation-PAL-U", "Redump.orgSonyPlayStation-PAL-V",
    "Redump.orgSonyPlayStation-PAL-W", "Redump.orgSonyPlayStation-PAL-X",
    "Redump.orgSonyPlayStation-PAL-Y", "Redump.orgSonyPlayStation-PAL-Z",
    # NTSC-J por letra
    "Redump.orgSonyPlayStation-NTSC-J-A", "Redump.orgSonyPlayStation-NTSC-J-B",
    "Redump.orgSonyPlayStation-NTSC-J-C", "Redump.orgSonyPlayStation-NTSC-J-D",
    "Redump.orgSonyPlayStation-NTSC-J-E", "Redump.orgSonyPlayStation-NTSC-J-F",
    "Redump.orgSonyPlayStation-NTSC-J-G", "Redump.orgSonyPlayStation-NTSC-J-H",
    "Redump.orgSonyPlayStation-NTSC-J-I", "Redump.orgSonyPlayStation-NTSC-J-J",
    "Redump.orgSonyPlayStation-NTSC-J-K", "Redump.orgSonyPlayStation-NTSC-J-L",
    "Redump.orgSonyPlayStation-NTSC-J-M", "Redump.orgSonyPlayStation-NTSC-J-N",
    "Redump.orgSonyPlayStation-NTSC-J-O", "Redump.orgSonyPlayStation-NTSC-J-P",
    "Redump.orgSonyPlayStation-NTSC-J-Q", "Redump.orgSonyPlayStation-NTSC-J-R",
    "Redump.orgSonyPlayStation-NTSC-J-S", "Redump.orgSonyPlayStation-NTSC-J-T",
    "Redump.orgSonyPlayStation-NTSC-J-U", "Redump.orgSonyPlayStation-NTSC-J-V",
    "Redump.orgSonyPlayStation-NTSC-J-W", "Redump.orgSonyPlayStation-NTSC-J-X",
    "Redump.orgSonyPlayStation-NTSC-J-Y", "Redump.orgSonyPlayStation-NTSC-J-Z",
    # Outras
    "redump_psx", "psx-roms-archive", "CuratedPSXRedumpCHDs",
    "Redump_PSX_2021_06_04_A_C", "Redump_PSX_2021_06_04_D_F",
    "Redump_PSX_2021_06_04_G_I", "Redump_PSX_2021_06_04_J_L",
    "Redump_PSX_2021_06_04_M_O", "Redump_PSX_2021_06_04_P_R",
    "Redump_PSX_2021_06_04_S_U", "Redump_PSX_2021_06_04_V_X",
    "Redump_PSX_2021_06_04_Y_Z",
    # CHD collections
    "SonyPSXISORedumpSet_2020-01-28_01",
    "SonyPSXISORedumpSet_2020-01-28_02",
    "SonyPSXISORedumpSet_2020-01-28_03",
    "SonyPSXISORedumpSet_2020-01-28_04",
    "SonyPSXISORedumpSet_2020-01-28_05",
    "SonyPSXISORedumpSet_2020-01-28_06",
    "SonyPSXISORedumpSet_2020-01-28_07",
    "SonyPSXISORedumpSet_2020-01-28_08",
]


def normalize_name(name):
    """Normaliza nome para matching: lowercase, sem acentos, sem pontuação."""
    name = name.lower()
    # Remover acentos
    replacements = {'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a',
                    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
                    'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
                    'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
                    'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
                    'ç': 'c', 'ñ': 'n'}
    for k, v in replacements.items():
        name = name.replace(k, v)
    # Remover pontuação, parênteses, colchetes
    name = re.sub(r'[^\w\s]', ' ', name)
    # Remover palavras comuns
    stop_words = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for',
                  'and', 'or', 'vol', 'series', 'psx', 'ps1', 'playstation',
                  'usa', 'europe', 'japan', 'pal', 'ntsc', 'disc', 'iso',
                  'bin', 'cue', 'zip', '7z', 'chd', 'rev', 'v1', 'v2',
                  'demo', 'beta', 'proto', 'alpha', 'unl', 'hack',
                  'rerelease', 're-release', 'best', 'hits'}
    words = [w for w in name.split() if w and w not in stop_words and len(w) > 1]
    return ' '.join(words)


def extract_game_name(filename):
    """Extrai nome do jogo de um nome de arquivo.
    Ex: 'SaGa Frontier (USA).zip' -> 'SaGa Frontier'
        'PlayStation/007 - The World Is Not Enough (USA).7z' -> '007 - The World Is Not Enough'
    """
    # Remover path
    basename = filename.split('/')[-1]
    # Remover extensão
    for ext in ROM_EXTS:
        if basename.lower().endswith(ext):
            basename = basename[:-len(ext)]
            break
    # Remover parênteses no final: (USA), (Europe), (Japan), (Disc 1), etc
    basename = re.sub(r'\s*[\(\[].*?[\)\]]\s*$', '', basename).strip()
    return basename


def extract_serial(filename):
    """Tenta extrair serial do nome do arquivo."""
    match = re.search(r'(S[LC][EUP]S?-\d{4,5})', filename.upper())
    return match.group(1) if match else None


def fetch_collection(coll):
    """Busca arquivos de uma collection."""
    url = f"http://archive.org/metadata/{coll}"
    try:
        r = s.get(url, timeout=(5, 30))
        if r.status_code == 200:
            data = r.json()
            files = data.get('files', [])
            roms = []
            for f in files:
                fname = f.get('name', '')
                fname_lower = fname.lower()
                if not any(fname_lower.endswith(ext) for ext in ROM_EXTS):
                    continue
                size = f.get('size', '0')
                serial = extract_serial(fname)
                game_name = extract_game_name(fname)
                roms.append({
                    'filename': fname,
                    'size': size,
                    'serial': serial,
                    'game_name': game_name,
                    'normalized': normalize_name(game_name),
                })
            return coll, roms
    except:
        pass
    return coll, []


def build_smart_index():
    """Constrói índice inteligente: por serial E por nome normalizado."""
    print(f"Construindo índice inteligente de {len(COLLECTIONS)} collections...", flush=True)

    by_serial = {}    # serial -> [(coll, filename, size)]
    by_name = {}      # normalized_name -> [(coll, filename, size, game_name)]
    all_roms = []

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(fetch_collection, c): c for c in COLLECTIONS}
        done = 0
        for f in as_completed(futures):
            coll = futures[f]
            done += 1
            try:
                _, roms = f.result()
                if roms:
                    print(f"  [{done}/{len(COLLECTIONS)}] {coll}: {len(roms)} ROMs", flush=True)
                for rom in roms:
                    all_roms.append({**rom, 'collection': coll})
                    # Indexar por serial
                    if rom['serial']:
                        if rom['serial'] not in by_serial:
                            by_serial[rom['serial']] = []
                        by_serial[rom['serial']].append({
                            'collection': coll, 'filename': rom['filename'], 'size': rom['size']
                        })
                    # Indexar por nome
                    if rom['normalized']:
                        if rom['normalized'] not in by_name:
                            by_name[rom['normalized']] = []
                        by_name[rom['normalized']].append({
                            'collection': coll, 'filename': rom['filename'],
                            'size': rom['size'], 'game_name': rom['game_name']
                        })
            except Exception as e:
                print(f"  [{done}/{len(COLLECTIONS)}] {coll}: erro {e}", flush=True)

    index = {
        'by_serial': by_serial,
        'by_name': by_name,
        'total_roms': len(all_roms),
        'total_serials': len(by_serial),
        'total_names': len(by_name),
        'built_at': time.time(),
    }

    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\nÍndice: {len(all_roms)} ROMs, {len(by_serial)} seriais, {len(by_name)} nomes", flush=True)
    return index


def load_smart_index():
    if os.path.exists(INDEX_PATH):
        mtime = os.path.getmtime(INDEX_PATH)
        if time.time() - mtime < 86400:
            with open(INDEX_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    return build_smart_index()


def fuzzy_match(name1, name2):
    """Match fuzzy entre dois nomes normalizados. Retorna score 0-100."""
    if not name1 or not name2:
        return 0
    w1 = set(name1.split())
    w2 = set(name2.split())
    if not w1 or not w2:
        return 0
    intersection = w1 & w2
    union = w1 | w2
    # Jaccard similarity
    jaccard = len(intersection) / len(union)
    # Cobertura: quantas palavras de name1 estão em name2
    coverage = len(intersection) / len(w1)
    return max(jaccard * 100, coverage * 80)


def search_rom(index, serial, name=''):
    """Busca ROM no índice por serial e/ou nome. Retorna lista de matches."""
    matches = []

    # 1. Busca por serial
    by_serial = index.get('by_serial', {})
    if serial.upper() in by_serial:
        for m in by_serial[serial.upper()]:
            matches.append({
                **m,
                'match_type': 'serial_exact',
                'score': 100,
            })

    # 2. Busca por nome (fuzzy)
    if name:
        norm = normalize_name(name)
        by_name = index.get('by_name', {})

        # Match exato de nome normalizado
        if norm in by_name:
            for m in by_name[norm]:
                matches.append({
                    **m,
                    'match_type': 'name_exact',
                    'score': 95,
                })

        # Match fuzzy — comparar com todos os nomes (limitado para performance)
        if not matches:
            best_score = 0
            best_matches = []
            for idx_name, entries in by_name.items():
                score = fuzzy_match(norm, idx_name)
                if score > best_score:
                    best_score = score
                    best_matches = [(score, e) for e in entries]
                elif score == best_score and score > 60:
                    best_matches.extend([(score, e) for e in entries])

            if best_score >= 60:
                for score, m in best_matches:
                    matches.append({
                        'collection': m['collection'],
                        'filename': m['filename'],
                        'size': m['size'],
                        'match_type': 'name_fuzzy',
                        'score': score,
                    })

    # Deduplicar e ordenar por score
    seen = set()
    unique = []
    for m in sorted(matches, key=lambda x: -x['score']):
        key = (m['collection'], m['filename'])
        if key not in seen:
            seen.add(key)
            unique.append(m)

    return unique


def build_download_url(collection, filename):
    return f"http://archive.org/download/{collection}/{quote(filename, safe='/')}"


def main():
    print("=" * 60, flush=True)
    print("SMART INDEX SEARCH — busca por serial E nome", flush=True)
    print("=" * 60, flush=True)

    index = load_smart_index()
    print(f"Índice: {index.get('total_roms', 0)} ROMs, {index.get('total_serials', 0)} seriais, {index.get('total_names', 0)} nomes\n", flush=True)

    # Carregar pendentes + failed
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

    print(f"Buscando {len(to_search)} ROMs...\n", flush=True)

    found = []
    not_found = []
    for item in to_search:
        serial = item.get('serial', '')
        name = item.get('name', '')
        matches = search_rom(index, serial, name)

        if matches:
            m = matches[0]  # Melhor match
            url = build_download_url(m['collection'], m['filename'])
            size_mb = int(m.get('size', '0')) / 1024 / 1024 if m.get('size', '0').isdigit() else 0
            print(f"  {serial}: ENCONTRADO [{m['match_type']}] score={m['score']} em {m['collection']}", flush=True)
            print(f"    arquivo: {m['filename']} ({size_mb:.1f}MB)", flush=True)
            print(f"    URL: {url[:100]}", flush=True)
            found.append({
                'serial': serial, 'name': name, 'url': url,
                'collection': m['collection'], 'filename': m['filename'],
                'size': m.get('size', '0'), 'score': m['score'],
                'match_type': m['match_type'],
            })
        else:
            print(f"  {serial}: não encontrado ({name[:40]})", flush=True)
            not_found.append(serial)

    print(f"\n=== RESULTADO ===", flush=True)
    print(f"Encontrados: {len(found)}", flush=True)
    print(f"Não encontrados: {len(not_found)}", flush=True)

    results_path = os.path.join(STATE_DIR, "smart_search_results.json")
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({'found': found, 'not_found': not_found}, f, ensure_ascii=False, indent=2)
    print(f"Resultados salvos em: {results_path}", flush=True)


if __name__ == '__main__':
    main()
