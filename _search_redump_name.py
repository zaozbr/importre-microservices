"""
Busca os 7 jogos falhados por NOME nas colecoes Redump.
Os arquivos Redump sao nomeados por nome do jogo, nao por serial.
"""
import json, sys, time, requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ARCHIVE_COOKIES = {
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Mapear jogos para colecoes provaveis por regiao
# SLPS/SLPM = Japan, SLES = PAL
FAILED = [
    ('SLPS-01224', 'MIRACLE JUMPERS', 'NTSC-J'),
    ('SLPS-01259', 'TOKYO 23KU SEIFUKU-WARS', 'NTSC-J'),
    ('SLPS-02366', 'TALL INFINITE', 'NTSC-J'),
    ('SLPM-86880', 'NUKUMORI NO NAKADE', 'NTSC-J'),
    ('SLPS-02346', 'WAKU WAKU VOLLEY', 'NTSC-J'),
    ('SLES-02693', 'GUTE ZEITEN SCHLECHTE', 'PAL'),
    ('SLES-01082', "DODGE'M", 'PAL'),
]

JP_COLLECTIONS = [
    'Redump.orgSonyPlayStation-NTSC-J-H',
    'Redump.orgSonyPlayStation-NTSC-J-K',
    'Redump.orgSonyPlayStation-NTSC-J-L-Z',
]
PAL_COLLECTIONS = [
    'Redump.orgSonyPlayStation-PAL-A-F',
    'Redump.orgSonyPlayStation-PAL-G-P',
    'Redump.orgSonyPlayStation-PAL-Q-Z',
]


def search_by_name(collection, name_parts):
    """Busca arquivos por palavras do nome do jogo."""
    try:
        url = f'https://archive.org/metadata/{collection}/files'
        r = requests.get(url, headers=HEADERS, cookies=ARCHIVE_COOKIES, timeout=30, verify=False)
        if r.status_code != 200:
            return []
        data = r.json()
        files = data.get('result', [])
        matches = []
        for f in files:
            fname = f.get('name', '')
            if not fname.endswith(('.zip', '.7z')):
                continue
            fname_lower = fname.lower()
            # Verificar se todas as palavras-chave estao no nome
            all_match = True
            for part in name_parts:
                if part.lower() not in fname_lower:
                    all_match = False
                    break
            if all_match:
                size = float(f.get('size', 0)) if f.get('size') else 0
                if size > 1024 * 1024:
                    matches.append({
                        'name': fname,
                        'size': size,
                        'url': f'https://archive.org/download/{collection}/{requests.utils.quote(fname)}',
                        'collection': collection,
                    })
        return matches
    except Exception as e:
        print(f'  Erro: {e}')
        return []


def main():
    print('=' * 60)
    print('  BUSCA POR NOME NAS COLECOES REDUMP')
    print('=' * 60)

    found = {}
    for serial, name, region in FAILED:
        print(f'\n--- {serial}: {name} ({region}) ---')
        cols = JP_COLLECTIONS if region == 'NTSC-J' else PAL_COLLECTIONS
        # Palavras-chave para buscar (remover palavras comuns)
        parts = [p for p in name.split() if len(p) > 2 and p.upper() not in ('THE', 'AND', 'VOL')]
        if not parts:
            parts = [name]
        print(f'  Palavras-chave: {parts}')

        for col in cols:
            matches = search_by_name(col, parts)
            if matches:
                for m in matches:
                    print(f'  ENCONTRADO: {m["name"]} ({m["size"]/1024/1024:.1f}MB)')
                    print(f'    URL: {m["url"]}')
                    if serial not in found:
                        found[serial] = m
            time.sleep(0.3)

        if serial not in found:
            # Tentar com menos palavras (primeira palavra apenas)
            if parts:
                print(f'  Tentando com: "{parts[0]}" apenas...')
                for col in cols:
                    matches = search_by_name(col, [parts[0]])
                    if matches:
                        for m in matches:
                            print(f'  CANDIDATO: {m["name"]} ({m["size"]/1024/1024:.1f}MB)')
                            print(f'    URL: {m["url"]}')
                    time.sleep(0.3)

    print(f'\n{"=" * 60}')
    print(f'  TOTAL ENCONTRADO: {len(found)}/7')
    print(f'{"=" * 60}')

    if found:
        q = json.load(open(r'D:\roms\library\roms\_importre_state\queue.json', encoding='utf-8'))
        failed = q.get('failed', {})
        queue = q.get('queue', [])
        for serial, info in found.items():
            failed.pop(serial, None)
            queue.append({
                'serial': serial,
                'name': dict((f[0], f[1]) for f in FAILED).get(serial, ''),
                'url': info['url'],
                'size': info['size'],
                'source': 'redump_name_search',
            })
            print(f'  {serial} re-adicionado a fila')
        q['failed'] = failed
        q['queue'] = queue
        q['total'] = len(queue) + len(q.get('in_progress', {})) + len(q.get('completed', {})) + len(failed)
        json.dump(q, open(r'D:\roms\library\roms\_importre_state\queue.json', 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'\nFila atualizada: {len(queue)} pendentes')


if __name__ == '__main__':
    main()
