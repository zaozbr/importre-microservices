"""
Busca ROMs no Myrient (myrient.erista.me) — serviço rápido de preservação.
Estrutura: /files/Redump/Sony/PlayStation/Games/
"""
import sys, os, time, json, re
from urllib.parse import quote, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STATE_DIR = r"D:\roms\library\roms\_importre_state"

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

# URLs base do Myrient
MYRIENT_BASES = [
    "https://myrient.erista.me/files/Redump/Sony/PlayStation/Games/",
    "https://myrient.erista.me/files/TOSEC-ISO/Sony/PlayStation/Games/[BIN]/",
    "https://myrient.erista.me/files/TOSEC-ISO/Sony/PlayStation/Games/[CHD]/",
    "https://dl23.myrient.erista.me/files/Redump/Sony/PlayStation/Games/",
]

ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')


def list_directory(url):
    """Lista arquivos em um diretório do Myrient (Apache directory listing)."""
    try:
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            files = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                name = a.get_text(strip=True)
                if href.endswith('/') and href != '../' and href != './':
                    # Subdiretório
                    files.append({'type': 'dir', 'name': unquote(href), 'url': url + href})
                elif any(href.lower().endswith(ext) for ext in ROM_EXTS):
                    files.append({'type': 'file', 'name': unquote(href), 'url': url + href})
            return files
    except:
        pass
    return []


def search_myrient(serial, name=''):
    """Busca ROM no Myrient listando diretórios."""
    all_files = []

    for base in MYRIENT_BASES:
        print(f"  Listando {base}...", flush=True)
        files = list_directory(base)
        print(f"    {len(files)} itens", flush=True)

        for f in files:
            if f['type'] == 'file':
                fname = f['name']
                # Verificar se o serial está no nome do arquivo
                serial_lower = serial.lower().replace('-', '')
                fname_lower = fname.lower().replace('-', '').replace('_', '').replace(' ', '')
                if serial_lower in fname_lower:
                    all_files.append({
                        'url': f['url'],
                        'filename': fname,
                        'score': 100,
                        'match_type': 'serial_exact',
                    })
                elif name:
                    # Match por nome
                    clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip().lower()
                    fname_clean = re.sub(r'\[.*?\]|\(.*?\)', '', fname).strip().lower()
                    if clean_name and len(clean_name) > 3 and clean_name[:20] in fname_clean:
                        all_files.append({
                            'url': f['url'],
                            'filename': fname,
                            'score': 70,
                            'match_type': 'name_partial',
                        })

            elif f['type'] == 'dir':
                # Listar subdiretório (apenas se o nome parecer relevante)
                dirname = f['name'].lower()
                serial_lower = serial.lower()
                # Se o diretório começa com a mesma letra que o serial
                if serial_lower[0] in dirname or serial_lower in dirname:
                    subfiles = list_directory(f['url'])
                    for sf in subfiles:
                        if sf['type'] == 'file':
                            fname = sf['name']
                            serial_lower_nohyphen = serial.lower().replace('-', '')
                            fname_lower = fname.lower().replace('-', '').replace('_', '').replace(' ', '')
                            if serial_lower_nohyphen in fname_lower:
                                all_files.append({
                                    'url': sf['url'],
                                    'filename': fname,
                                    'score': 100,
                                    'match_type': 'serial_in_subdir',
                                })

    # Deduplicar
    seen = set()
    unique = []
    for f in all_files:
        if f['url'] not in seen:
            seen.add(f['url'])
            unique.append(f)

    return sorted(unique, key=lambda x: -x['score'])


def main():
    print("=" * 60, flush=True)
    print("MYRIENT SEARCH — busca em myrient.erista.me", flush=True)
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

    print(f"Buscando {len(to_search)} ROMs no Myrient...\n", flush=True)

    # Primeiro listar todos os arquivos das bases
    all_roms = []
    for base in MYRIENT_BASES:
        print(f"Listando {base}...", flush=True)
        files = list_directory(base)
        print(f"  {len(files)} itens", flush=True)
        for f in files:
            if f['type'] == 'file':
                all_roms.append(f)

    print(f"\nTotal de arquivos ROM: {len(all_roms)}\n", flush=True)

    # Buscar cada ROM pendente
    found = []
    for item in to_search:
        serial = item.get('serial', '')
        name = item.get('name', '')

        serial_lower = serial.lower().replace('-', '')
        matches = []
        for rom in all_roms:
            fname = rom['name']
            fname_lower = fname.lower().replace('-', '').replace('_', '').replace(' ', '')
            if serial_lower in fname_lower:
                matches.append((100, rom))
            elif name:
                clean = re.sub(r'\[.*?\]|\(.*?\)', '', name).strip().lower()
                if clean and len(clean) > 3 and clean[:15] in fname.lower():
                    matches.append((70, rom))

        if matches:
            matches.sort(key=lambda x: -x[0])
            best = matches[0][1]
            print(f"  {serial}: ENCONTRADO — {best['name']}", flush=True)
            print(f"    URL: {best['url'][:100]}", flush=True)
            found.append({
                'serial': serial, 'name': name,
                'url': best['url'], 'filename': best['name'],
                'score': matches[0][0],
            })
        else:
            print(f"  {serial}: não encontrado", flush=True)

    print(f"\n=== RESULTADO ===", flush=True)
    print(f"Encontrados: {len(found)}", flush=True)

    results_path = os.path.join(STATE_DIR, "myrient_results.json")
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(found, f, ensure_ascii=False, indent=2)
    print(f"Resultados salvos em: {results_path}", flush=True)


if __name__ == '__main__':
    main()
