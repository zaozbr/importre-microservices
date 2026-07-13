"""
Busca os 7 jogos falhados diretamente na colecao Redump do archive.org.
A colecao Redump tem os jogos organizados por serial nos nomes dos arquivos.
"""
import json, sys, time, requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ARCHIVE_COOKIES = {
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Colecoes Redump do archive.org
COLLECTIONS = [
    'Redump.orgSonyPlayStation-NTSC-J-H',
    'Redump.orgSonyPlayStation-NTSC-J-K',
    'Redump.orgSonyPlayStation-NTSC-J-L-Z',
    'Redump.orgSonyPlayStation-NTSC-U-H',
    'Redump.orgSonyPlayStation-PAL-A-F',
    'Redump.orgSonyPlayStation-PAL-G-P',
    'Redump.orgSonyPlayStation-PAL-Q-Z',
]

FAILED = [
    ('SLPS-01224', 'MIRACLE JUMPERS'),
    ('SLPS-01259', 'TOKYO 23KU SEIFUKU-WARS'),
    ('SLPS-02366', 'TALL INFINITE'),
    ('SLPM-86880', 'NUKUMORI NO NAKADE IN THE WARMTH'),
    ('SLPS-02346', 'WAKU WAKU VOLLEY'),
    ('SLES-02693', 'GUTE ZEITEN SCHLECHTE QUIZ'),
    ('SLES-01082', "DODGE'M ARENA"),
]


def search_collection_files(collection, serial):
    """Busca arquivos de uma colecao que contenham o serial no nome."""
    try:
        url = f'https://archive.org/metadata/{collection}/files'
        r = requests.get(url, headers=HEADERS, cookies=ARCHIVE_COOKIES, timeout=30, verify=False)
        if r.status_code != 200:
            return []
        data = r.json()
        files = data.get('result', [])
        matches = []
        serial_lower = serial.lower().replace('-', '')
        for f in files:
            name = f.get('name', '')
            name_lower = name.lower().replace('-', '').replace('_', '').replace(' ', '')
            if serial_lower in name_lower:
                size = float(f.get('size', 0)) if f.get('size') else 0
                if size > 1024 * 1024:  # > 1MB
                    matches.append({
                        'name': name,
                        'size': size,
                        'url': f'https://archive.org/download/{collection}/{requests.utils.quote(name)}',
                        'collection': collection,
                    })
        return matches
    except Exception as e:
        print(f'  Erro: {e}')
        return []


def main():
    print('=' * 60)
    print('  BUSCA NA COLECAO REDUMP (archive.org)')
    print('=' * 60)

    found = {}
    for serial, name in FAILED:
        print(f'\n--- {serial}: {name} ---')
        for col in COLLECTIONS:
            matches = search_collection_files(col, serial)
            if matches:
                for m in matches:
                    print(f'  ENCONTRADO: {m["name"]} ({m["size"]/1024/1024:.1f}MB)')
                    print(f'    URL: {m["url"]}')
                    if serial not in found:
                        found[serial] = m
                break
        else:
            print(f'  NAO encontrado em nenhuma colecao')
        time.sleep(0.5)

    print(f'\n{"=" * 60}')
    print(f'  TOTAL ENCONTRADO: {len(found)}/7')
    print(f'{"=" * 60}')

    if found:
        # Adicionar de volta na fila
        q = json.load(open(r'D:\roms\library\roms\_importre_state\queue.json', encoding='utf-8'))
        failed = q.get('failed', {})
        queue = q.get('queue', [])
        for serial, info in found.items():
            # Remover de failed
            failed.pop(serial, None)
            # Adicionar na fila
            queue.append({
                'serial': serial,
                'name': dict(FAILED).get(serial, ''),
                'url': info['url'],
                'size': info['size'],
                'source': 'redump_search',
            })
            print(f'  {serial} re-adicionado a fila')

        q['failed'] = failed
        q['queue'] = queue
        q['total'] = len(queue) + len(q.get('in_progress', {})) + len(q.get('completed', {})) + len(failed)
        json.dump(q, open(r'D:\roms\library\roms\_importre_state\queue.json', 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'\nFila atualizada: {len(queue)} pendentes')


if __name__ == '__main__':
    main()
