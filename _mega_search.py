"""
Mega Search: busca os 592 ROMs comerciais faltantes navegando coleções do archive.org.

Estratégia:
1. Para cada ROM faltante, buscar no archive.org via advancedsearch (múltiplas queries)
2. Se encontrar, resolver metadata e obter URL de download
3. Tentar download direto primeiro (mais rápido)
4. Se 401/403, tentar via Tor paralelo
5. Se não encontrar no archive.org, tentar outras fontes (coolrom, etc)

Funciona em batch: processa todos os ROMs, encontra URLs, depois baixa em paralelo.
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

STATE_DIR = r'D:\roms\library\roms\_importre_state'
RESULTS_PATH = os.path.join(STATE_DIR, 'mega_search_results.json')
ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})


def advanced_search(query, rows=100):
    url = f"http://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&fl[]=title&rows={rows}&page=1&output=json"
    try:
        r = s.get(url, timeout=(5, 20))
        if r.status_code == 200:
            return r.json().get('response', {}).get('docs', [])
    except:
        pass
    return []


def get_metadata(identifier):
    url = f"http://archive.org/metadata/{identifier}"
    try:
        r = s.get(url, timeout=(5, 15))
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def extract_serial(text):
    match = re.search(r'(S[LC][EUP]S?-\d{4,5}|SCUS-\d{5})', text.upper())
    return match.group(1) if match else None


def search_rom(serial, name=''):
    """Busca um ROM no archive.org com múltiplas estratégias."""
    all_ids = []

    # Query 1: serial exato entre aspas
    docs = advanced_search(f'"{serial}"', rows=50)
    all_ids.extend([(d['identifier'], 100) for d in docs if 'identifier' in d])

    # Query 2: serial sem hifem
    serial_no = serial.replace('-', ' ')
    docs = advanced_search(f'{serial_no} playstation', rows=50)
    all_ids.extend([(d['identifier'], 80) for d in docs if 'identifier' in d])

    # Query 3: serial + collection redump
    docs = advanced_search(f'{serial} AND (collection:redump OR collection:sony_playstation OR collection:console)', rows=50)
    all_ids.extend([(d['identifier'], 90) for d in docs if 'identifier' in d])

    # Query 4: por nome do jogo
    if name:
        clean = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip()
        if clean and len(clean) > 3:
            # Primeiras palavras significativas
            words = [w for w in clean.split() if len(w) > 2 and w.lower() not in
                     ('the', 'and', 'for', 'vol', 'series', 'disc')]
            if words:
                partial = ' '.join(words[:3])
                docs = advanced_search(f'"{partial}" playstation', rows=50)
                all_ids.extend([(d['identifier'], 60) for d in docs if 'identifier' in d])

    # Query 5: serial + mediatype software
    docs = advanced_search(f'{serial} AND mediatype:software', rows=50)
    all_ids.extend([(d['identifier'], 85) for d in docs if 'identifier' in d])

    # Deduplicar mantendo maior score
    best = {}
    for ident, score in all_ids:
        if ident not in best or score > best[ident]:
            best[ident] = score

    return sorted(best.items(), key=lambda x: -x[1])


def resolve_to_url(identifier, serial):
    """Busca metadata do item e encontra arquivo ROM com o serial."""
    data = get_metadata(identifier)
    if not data:
        return None, None, None

    files = data.get('files', [])
    if not files:
        return None, None, None

    serial_lower = serial.lower().replace('-', '')
    serial_underscore = serial.lower().replace('-', '_')
    serial_space = serial.lower().replace('-', ' ')

    candidates = []
    for f in files:
        fname = f.get('name', '')
        fname_lower = fname.lower()
        if not any(fname_lower.endswith(ext) for ext in ROM_EXTS):
            continue
        score = 0
        # Match por serial no nome do arquivo
        fname_normalized = fname_lower.replace('-', '').replace('_', '').replace(' ', '')
        if serial_lower in fname_normalized:
            score = 100
        elif serial_underscore in fname_lower:
            score = 80
        elif serial_space in fname_lower:
            score = 70
        elif serial.lower() in fname_lower:
            score = 60
        # Bonus para formatos compactados
        if fname_lower.endswith(('.zip', '.7z', '.chd')):
            score += 5
        # Verificar tamanho (ROMs PSX sao > 5MB)
        try:
            size = int(f.get('size', '0'))
            if size > 5 * 1024 * 1024:
                score += 5
            elif size < 1024 * 1024:
                score -= 20  # Muito pequeno, provavelmente nao e ROM
        except:
            pass
        candidates.append((score, fname, f.get('size', '0')))

    if not candidates:
        # Fallback: pegar primeiro arquivo ROM
        for f in files:
            fname = f.get('name', '')
            if any(fname.lower().endswith(ext) for ext in ROM_EXTS):
                candidates.append((0, fname, f.get('size', '0')))
                break

    if not candidates:
        return None, None, None

    candidates.sort(key=lambda x: -x[0])
    best_score, best_fname, best_size = candidates[0]

    # Se o melhor score e muito baixo, provavelmente nao e o ROM certo
    if best_score < 20:
        return None, None, None

    url = f"http://archive.org/download/{identifier}/{quote(best_fname, safe='/')}"
    return url, best_fname, best_size


def search_one_rom(serial, name):
    """Busca um ROM e retorna resultado completo."""
    results = search_rom(serial, name)

    for ident, score in results[:15]:
        url, fname, size = resolve_to_url(ident, serial)
        if url:
            return {
                'serial': serial,
                'name': name,
                'identifier': ident,
                'url': url,
                'filename': fname,
                'size': size,
                'score': score,
            }

    return None


def main():
    print("=" * 70, flush=True)
    print("MEGA SEARCH — buscando 592 ROMs faltantes no archive.org", flush=True)
    print("=" * 70, flush=True)

    # Carregar faltantes
    with open(os.path.join(STATE_DIR, 'missing_analysis.json'), 'r', encoding='utf-8') as f:
        analysis = json.load(f)

    missing = analysis.get('missing_commercial', {})
    print(f"Total faltantes: {len(missing)}\n", flush=True)

    # Carregar resultados anteriores se existir
    found = []
    not_found = []
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, 'r', encoding='utf-8') as f:
            prev = json.load(f)
            found = prev.get('found', [])
            not_found = prev.get('not_found', [])
            print(f"Resultados anteriores: {len(found)} encontrados, {len(not_found)} nao encontrados\n", flush=True)

    # Pular seriais ja encontrados
    found_serials = {r['serial'] for r in found}
    to_search = {s: n for s, n in missing.items() if s not in found_serials and s not in not_found}

    print(f"Para buscar: {len(to_search)}\n", flush=True)

    # Buscar em paralelo (10 threads)
    batch_size = 50
    all_to_search = list(to_search.items())

    for batch_start in range(0, len(all_to_search), batch_size):
        batch = all_to_search[batch_start:batch_start + batch_size]
        print(f"\n--- Batch {batch_start//batch_size + 1}/{(len(all_to_search)-1)//batch_size + 1} ({len(batch)} ROMs) ---", flush=True)

        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(search_one_rom, serial, name): serial for serial, name in batch}
            for f in as_completed(futures):
                serial = futures[f]
                try:
                    result = f.result()
                    if result:
                        found.append(result)
                        print(f"  [OK] {serial}: {result['identifier']} -> {result['filename'][:40]}", flush=True)
                    else:
                        not_found.append(serial)
                        name = missing.get(serial, '')
                        print(f"  [--] {serial}: nao encontrado ({name[:30]})", flush=True)
                except Exception as e:
                    not_found.append(serial)
                    print(f"  [ER] {serial}: {e}", flush=True)

        # Salvar progresso a cada batch
        with open(RESULTS_PATH, 'w', encoding='utf-8') as f:
            json.dump({'found': found, 'not_found': not_found}, f, ensure_ascii=False, indent=2)

    print(f"\n=== RESULTADO FINAL ===", flush=True)
    print(f"Encontrados: {len(found)}", flush=True)
    print(f"Nao encontrados: {len(not_found)}", flush=True)
    print(f"Salvo em: {RESULTS_PATH}", flush=True)


if __name__ == '__main__':
    main()
