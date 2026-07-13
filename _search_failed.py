"""
Tenta baixar os 7 jogos falhados usando estrategias alternativas:
1. Busca por nome (sem serial)
2. Busca em colecoes JP
3. Busca por variacoes de serial
"""
import json, os, sys, time, requests
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

QUEUE_PATH = r'D:\roms\library\roms\_importre_state\queue.json'
DOWNLOADS_DIR = r'D:\roms\library\roms\_importre_state\downloads'

ARCHIVE_COOKIES = {
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
}

FAILED_GAMES = [
    ('SLPS-01224', 'MIRACLE JUMPERS'),
    ('SLPS-01259', 'TOKYO 23KU SEIFUKU-WARS'),
    ('SLPS-02366', 'TALL INFINITE'),
    ('SLPM-86880', 'NUKUMORI NO NAKADE IN THE WARMTH'),
    ('SLPS-02346', 'WAKU WAKU VOLLEY'),
    ('SLES-02693', 'GUTE ZEITEN SCHLECHTE QUIZ'),
    ('SLES-01082', "DODGE'M ARENA"),
]


def search_archive(serial, name):
    """Busca no archive.org por nome e serial."""
    results = []
    # Busca por nome
    for query in [name, serial, f'{name} psx', f'{name} playstation']:
        try:
            url = f'https://archive.org/advancedsearch.php?q={requests.utils.quote(query)}%20AND%20mediatype%3A%28software%29&fl[]=identifier&fl[]=title&fl[]=size&rows=10&page=1&output=json'
            r = requests.get(url, headers=HEADERS, cookies=ARCHIVE_COOKIES, timeout=15, verify=False)
            if r.status_code == 200:
                data = r.json()
                docs = data.get('response', {}).get('docs', [])
                for doc in docs:
                    results.append({
                        'identifier': doc.get('identifier', ''),
                        'title': doc.get('title', ''),
                        'size': doc.get('size', 0),
                        'query': query,
                    })
        except Exception as e:
            print(f'  Erro buscando "{query}": {e}')
        time.sleep(0.5)
    return results


def get_archive_files(identifier):
    """Lista arquivos de um item do archive.org."""
    try:
        url = f'https://archive.org/metadata/{identifier}/files'
        r = requests.get(url, headers=HEADERS, cookies=ARCHIVE_COOKIES, timeout=15, verify=False)
        if r.status_code == 200:
            data = r.json()
            files = data.get('result', [])
            rom_files = []
            for f in files:
                name = f.get('name', '')
                if name.endswith(('.bin', '.img', '.iso', '.zip', '.7z', '.rar')):
                    rom_files.append({
                        'name': name,
                        'size': f.get('size', 0),
                        'url': f'https://archive.org/download/{identifier}/{requests.utils.quote(name)}',
                    })
            return rom_files
    except Exception as e:
        print(f'  Erro listando arquivos: {e}')
    return []


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print('=' * 60)
    print('  BUSCA ALTERNATIVA PARA 7 JOGOS FALHADOS')
    print('=' * 60)

    found = []
    for serial, name in FAILED_GAMES:
        print(f'\n--- {serial}: {name} ---')
        results = search_archive(serial, name)
        # Deduplicar por identifier
        seen = set()
        unique = []
        for r in results:
            if r['identifier'] not in seen:
                seen.add(r['identifier'])
                unique.append(r)
        print(f'  {len(unique)} resultados unicos')
        for r in unique[:5]:
            size_mb = float(r["size"]) / 1024 / 1024 if r["size"] else 0
            print(f'    {r["identifier"]} - {r["title"]} ({size_mb:.1f}MB) [query: {r["query"]}]')
            # Verificar arquivos
            files = get_archive_files(r['identifier'])
            for f in files[:3]:
                fsize = float(f["size"]) if f["size"] else 0
                print(f'      -> {f["name"]} ({fsize/1024/1024:.1f}MB)')
                if fsize > 1024 * 1024:  # > 1MB
                    found.append({
                        'serial': serial,
                        'name': name,
                        'identifier': r['identifier'],
                        'file': f,
                    })
            time.sleep(0.3)

    print(f'\n{"=" * 60}')
    print(f'  ENCONTRADOS: {len(found)} arquivos candidatos')
    print(f'{"=" * 60}')
    for f in found:
        fsize = float(f["file"]["size"]) if f["file"]["size"] else 0
        print(f'  {f["serial"]}: {f["file"]["name"]} ({fsize/1024/1024:.1f}MB)')
        print(f'    URL: {f["file"]["url"]}')

    # Salvar resultados
    results_path = r'D:\roms\library\roms\_importre_state\failed_search_results.json'
    with open(results_path, 'w', encoding='utf-8') as rf:
        json.dump(found, rf, ensure_ascii=False, indent=2)
    print(f'\nResultados salvos em: {results_path}')


if __name__ == '__main__':
    main()
