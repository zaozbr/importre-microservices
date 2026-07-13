"""Verifica acessibilidade de mais coleções do archive.org."""
import requests, json
from urllib.parse import quote

s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})

# Coleções adicionais para testar
COLLECTIONS = [
    'chd_psx',
    'Sony-Playstation-USA-Redump.org-2020-07-24',
    'sony-playstation-a-redump-collection',
    'Sony-Playstation-Europe-Redump.org-2020-07-24',
    'Sony-Playstation-Japan-Redump.org-2020-07-24',
    'psx-redump',
    'Sony-PlayStation-Redump',
    'redump-sony-playstation',
    'SonyPlayStationRedump',
    'psx_chd',
    'PSX_CHD',
    'psx-redump-chd',
    'Sony-PlayStation-Redump-Collection',
    'PlayStation-Redump',
    'psx_iso',
    'PSX_Games',
    'psx-games',
    'playstation-games',
    'Sony-PlayStation-Games',
    'ps1-games',
    'PS1_Games',
    'playstation-1-games',
    'Sony-PlayStation-USA',
    'Sony-PlayStation-Europe',
    'Sony-PlayStation-Japan',
    'psx-usa',
    'psx-europe',
    'psx-japan',
    'Sony-PlayStation-PS1-Redump',
    'Redump-Sony-PlayStation',
    'psx-redump-set',
    'PSX-Redump-Set',
    'Sony-PSX-Redump',
    'sony-psx-redump',
    'PlayStation-PSX-Redump',
    'playstation-psx-redump',
]

ROM_EXTS = ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp')

accessible = []
restricted = []

for coll in COLLECTIONS:
    url = f'http://archive.org/metadata/{coll}'
    try:
        r = s.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            files = data.get('files', [])
            rom_count = sum(1 for f in files if any(f.get('name', '').lower().endswith(ext) for ext in ROM_EXTS))
            if rom_count > 0:
                # Testar download do primeiro ROM
                rom_file = None
                for f in files:
                    fname = f.get('name', '')
                    if any(fname.lower().endswith(ext) for ext in ROM_EXTS):
                        rom_file = fname
                        break
                if rom_file:
                    dl_url = f'http://archive.org/download/{coll}/{quote(rom_file, safe="/")}'
                    r2 = s.get(dl_url, timeout=10, stream=True)
                    status = r2.status_code
                    r2.close()
                    if status == 200:
                        accessible.append((coll, rom_count))
                        print(f'  [ACCESSIVEL] {coll}: {rom_count} ROMs (download 200)')
                    else:
                        restricted.append((coll, rom_count, status))
                        print(f'  [RESTRITA] {coll}: {rom_count} ROMs (download {status})')
            else:
                print(f'  [VAZIA] {coll}: sem ROMs')
    except:
        print(f'  [ERRO] {coll}: falha ao acessar')

print(f'\n=== RESUMO ===')
print(f'Acessiveis: {len(accessible)}')
for coll, count in accessible:
    print(f'  {coll}: {count} ROMs')
print(f'Restritas: {len(restricted)}')
for coll, count, status in restricted:
    print(f'  {coll}: {count} ROMs (HTTP {status})')

# Salvar
with open(r'D:\roms\library\roms\_importre_state\accessible_collections.json', 'w') as f:
    json.dump({'accessible': accessible, 'restricted': restricted}, f, indent=2)
