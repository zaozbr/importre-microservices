"""
Busca os 7 jogos falhados em fontes alternativas:
- Vimm.net
- CoolROM
- Romulation
- ConsoleRoms
Usando requests diretos (sem Playwright para ser mais rapido).
"""
import json, sys, time, requests, re, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

FAILED = [
    ('SLPS-01224', 'MIRACLE JUMPERS', 'NTSC-J'),
    ('SLPS-01259', 'TOKYO 23KU SEIFUKU-WARS', 'NTSC-J'),
    ('SLPS-02366', 'TALL INFINITE', 'NTSC-J'),
    ('SLPM-86880', 'NUKUMORI NO NAKADE', 'NTSC-J'),
    ('SLPS-02346', 'WAKU WAKU VOLLEY', 'NTSC-J'),
    ('SLES-02693', 'GUTE ZEITEN SCHLECHTE', 'PAL'),
    ('SLES-01082', "DODGEM ARENA", 'PAL'),
]


def search_vimm(serial, name):
    """Busca no Vimm.net por nome."""
    try:
        url = f'https://vimm.net/vault/?action=search&search={requests.utils.quote(name)}&system=PS1'
        r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if r.status_code == 200:
            # Procurar links de jogos
            matches = re.findall(r'href="/vault/(\d+)"[^>]*>([^<]+)', r.text)
            results = []
            for id, title in matches:
                if any(word.lower() in title.lower() for word in name.split() if len(word) > 3):
                    results.append({
                        'source': 'vimm',
                        'id': id,
                        'title': title,
                        'url': f'https://vimm.net/vault/{id}',
                    })
            return results
    except Exception as e:
        print(f'  Vimm erro: {e}')
    return []


def search_coolrom(name):
    """Busca no CoolROM por nome."""
    try:
        url = f'https://www.coolrom.com/search?q={requests.utils.quote(name)}&system=psx'
        r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if r.status_code == 200:
            # Procurar links
            matches = re.findall(r'href="(/roms/psx/(\d+)/[^"]+)"[^>]*>([^<]+)', r.text)
            results = []
            for path, id, title in matches:
                results.append({
                    'source': 'coolrom',
                    'id': id,
                    'title': title,
                    'url': f'https://www.coolrom.com{path}',
                })
            return results
    except Exception as e:
        print(f'  CoolROM erro: {e}')
    return []


def search_romulation(serial, name):
    """Busca no Romulation por serial."""
    try:
        url = f'https://www.romulation.org/search/?q={requests.utils.quote(serial)}'
        r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if r.status_code == 200:
            matches = re.findall(r'href="(/rom/(\d+)[^"]*)"[^>]*>([^<]+)', r.text)
            results = []
            for path, id, title in matches:
                if 'psx' in path.lower() or 'playstation' in title.lower():
                    results.append({
                        'source': 'romulation',
                        'id': id,
                        'title': title,
                        'url': f'https://www.romulation.org{path}',
                    })
            return results
    except Exception as e:
        print(f'  Romulation erro: {e}')
    return []


def main():
    print('=' * 60)
    print('  BUSCA EM FONTES ALTERNATIVAS')
    print('=' * 60)

    all_found = {}
    for serial, name, region in FAILED:
        print(f'\n--- {serial}: {name} ---')
        # Vimm
        results = search_vimm(serial, name)
        if results:
            print(f'  Vimm: {len(results)} resultados')
            for r in results[:3]:
                print(f'    {r["title"]} -> {r["url"]}')
                if serial not in all_found:
                    all_found[serial] = r
        time.sleep(0.5)

        # CoolROM
        results = search_coolrom(name)
        if results:
            print(f'  CoolROM: {len(results)} resultados')
            for r in results[:3]:
                print(f'    {r["title"]} -> {r["url"]}')
                if serial not in all_found:
                    all_found[serial] = r
        time.sleep(0.5)

        # Romulation
        results = search_romulation(serial, name)
        if results:
            print(f'  Romulation: {len(results)} resultados')
            for r in results[:3]:
                print(f'    {r["title"]} -> {r["url"]}')
                if serial not in all_found:
                    all_found[serial] = r
        time.sleep(0.5)

    print(f'\n{"=" * 60}')
    print(f'  TOTAL ENCONTRADO: {len(all_found)}/7')
    print(f'{"=" * 60}')
    for serial, info in all_found.items():
        print(f'  {serial}: {info["source"]} - {info["title"]}')
        print(f'    URL: {info["url"]}')

    # Salvar resultados
    results_path = r'D:\roms\library\roms\_importre_state\alt_source_results.json'
    with open(results_path, 'w', encoding='utf-8') as rf:
        json.dump(all_found, rf, ensure_ascii=False, indent=2)
    print(f'\nResultados salvos em: {results_path}')


if __name__ == '__main__':
    main()
