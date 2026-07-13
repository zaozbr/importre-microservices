"""
EMERGENCIA: Cruza os 325 ROMs nao encontrados com o smart_index_expanded.
Tambem busca por nome fuzzy com threshold mais baixo (50 em vez de 65).
"""
import sys, os, time, json, re
from urllib.parse import quote

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STATE_DIR = r'D:\roms\library\roms\_importre_state'
EXPANDED_PATH = os.path.join(STATE_DIR, 'smart_index_expanded.json')
RESULTS_PATH = os.path.join(STATE_DIR, 'cross_index_v2_results.json')


def normalize_name(name):
    name = name.lower()
    replacements = {'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a',
                    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
                    'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
                    'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
                    'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
                    'ç': 'c', 'ñ': 'n'}
    for k, v in replacements.items():
        name = name.replace(k, v)
    name = re.sub(r'[^\w\s]', ' ', name)
    stop_words = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for',
                  'and', 'or', 'vol', 'series', 'psx', 'ps1', 'playstation',
                  'usa', 'europe', 'japan', 'pal', 'ntsc', 'disc', 'iso',
                  'bin', 'cue', 'zip', '7z', 'chd', 'rev', 'v1', 'v2',
                  'demo', 'beta', 'proto', 'alpha', 'unl', 'hack'}
    words = [w for w in name.split() if w and w not in stop_words and len(w) > 1]
    return ' '.join(words)


def fuzzy_match(name1, name2):
    if not name1 or not name2:
        return 0
    w1 = set(name1.split())
    w2 = set(name2.split())
    if not w1 or not w2:
        return 0
    intersection = w1 & w2
    union = w1 | w2
    jaccard = len(intersection) / len(union)
    coverage = len(intersection) / len(w1)
    return max(jaccard * 100, coverage * 80)


def main():
    print("=" * 70, flush=True)
    print("CROSS INDEX V2 — buscando 325 ROMs no indice expandido", flush=True)
    print("=" * 70, flush=True)

    # Carregar indice expandido
    if not os.path.exists(EXPANDED_PATH):
        print("smart_index_expanded.json nao encontrado. Rode _expand_index.py primeiro.", flush=True)
        return

    with open(EXPANDED_PATH, 'r', encoding='utf-8') as f:
        index = json.load(f)

    by_serial = index.get('by_serial', {})
    by_name = index.get('by_name', {})
    print(f"Indice: {index.get('total_roms', 0)} ROMs, {len(by_serial)} seriais, {len(by_name)} nomes\n", flush=True)

    # Carregar faltantes
    with open(os.path.join(STATE_DIR, 'missing_analysis.json'), 'r', encoding='utf-8') as f:
        analysis = json.load(f)
    missing = analysis.get('missing_commercial', {})

    # Carregar nao encontrados pelo cross_index v1
    with open(os.path.join(STATE_DIR, 'cross_index_results.json'), 'r', encoding='utf-8') as f:
        cross = json.load(f)
    cross_found_serials = {r['serial'] for r in cross.get('found', [])}
    cross_not_found = set(cross.get('not_found', []))

    # ROMs para buscar = nao encontrados pelo cross_index v1
    to_search = {s: missing[s] for s in cross_not_found if s in missing}
    print(f"Para buscar: {len(to_search)}\n", flush=True)

    found = []
    not_found = []

    for serial, name in sorted(to_search.items()):
        matches = []

        # 1. Busca por serial exato
        if serial.upper() in by_serial:
            for m in by_serial[serial.upper()]:
                matches.append({
                    'collection': m['collection'],
                    'filename': m['filename'],
                    'size': m.get('size', '0'),
                    'url': f"http://archive.org/download/{m['collection']}/{quote(m['filename'], safe='/')}",
                    'match_type': 'serial_exact',
                    'score': 100,
                })

        # 2. Busca por serial com variacoes
        if not matches:
            serial_variants = [
                serial.upper().replace('-', ''),
                serial.upper().replace('-', '_'),
                serial.upper().replace('-', ' '),
            ]
            for variant in serial_variants:
                for idx_serial, entries in by_serial.items():
                    if variant in idx_serial.replace('-', '').replace('_', '').replace(' ', ''):
                        for m in entries:
                            matches.append({
                                'collection': m['collection'],
                                'filename': m['filename'],
                                'size': m.get('size', '0'),
                                'url': f"http://archive.org/download/{m['collection']}/{quote(m['filename'], safe='/')}",
                                'match_type': 'serial_variant',
                                'score': 90,
                            })

        # 3. Busca por nome exato
        if not matches and name:
            norm = normalize_name(name)
            if norm and len(norm) > 3:
                if norm in by_name:
                    for m in by_name[norm]:
                        matches.append({
                            'collection': m['collection'],
                            'filename': m['filename'],
                            'size': m.get('size', '0'),
                            'url': f"http://archive.org/download/{m['collection']}/{quote(m['filename'], safe='/')}",
                            'match_type': 'name_exact',
                            'score': 95,
                        })

                # 4. Busca por nome fuzzy (threshold mais baixo: 50)
                if not matches:
                    best_score = 0
                    best_entries = []
                    for idx_name, entries in by_name.items():
                        score = fuzzy_match(norm, idx_name)
                        if score > best_score:
                            best_score = score
                            best_entries = entries
                        elif score == best_score and score > 50:
                            best_entries.extend(entries)

                    if best_score >= 50:
                        for m in best_entries[:3]:
                            matches.append({
                                'collection': m['collection'],
                                'filename': m['filename'],
                                'size': m.get('size', '0'),
                                'url': f"http://archive.org/download/{m['collection']}/{quote(m['filename'], safe='/')}",
                                'match_type': 'name_fuzzy',
                                'score': best_score,
                            })

        # Deduplicar
        seen = set()
        unique = []
        for m in sorted(matches, key=lambda x: -x['score']):
            key = (m['collection'], m['filename'])
            if key not in seen:
                seen.add(key)
                unique.append(m)

        if unique:
            best = unique[0]
            found.append({
                'serial': serial,
                'name': name,
                'url': best['url'],
                'collection': best['collection'],
                'filename': best['filename'],
                'size': best['size'],
                'score': best['score'],
                'match_type': best['match_type'],
            })
            print(f"  [OK] {serial}: [{best['match_type']}] {best['collection'][:30]} -> {best['filename'][:40]}", flush=True)
        else:
            not_found.append(serial)

    print(f"\n=== RESULTADO ===", flush=True)
    print(f"Encontrados: {len(found)}", flush=True)
    print(f"Nao encontrados: {len(not_found)}", flush=True)

    with open(RESULTS_PATH, 'w', encoding='utf-8') as f:
        json.dump({'found': found, 'not_found': not_found}, f, ensure_ascii=False, indent=2)
    print(f"Salvo em: {RESULTS_PATH}", flush=True)


if __name__ == '__main__':
    main()
