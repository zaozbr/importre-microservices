import json, os

jp_path = r'D:\roms\library\roms\_importre_state\archive_jp_index.json'
if os.path.exists(jp_path):
    with open(jp_path) as f:
        jp = json.load(f)
    print(f'Indice JP: {len(jp)} entradas')

    with open(r'D:\roms\library\roms\_importre_state\cross_index_results.json') as f:
        cross = json.load(f)
    not_found = set(cross.get('not_found', []))

    found_jp = [s for s in not_found if s in jp or s.upper() in jp]
    print(f'Encontrados no indice JP: {len(found_jp)}')
    for s in found_jp[:20]:
        val = jp.get(s) or jp.get(s.upper())
        print(f'  {s}: {str(val)[:80]}')
else:
    print('Indice JP nao encontrado')
