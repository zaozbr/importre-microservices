import requests, json
from urllib.parse import quote

# Search archive.org for game titles in clearancebin collection
games = [
    ('SLUS-00510', 'Vigilante 8'),
    ('SLUS-00640', 'RPG Maker'),
    ('SLUS-00901', 'Motocross Madness'),
    ('SLES-00327', 'Wipeout 2097'),
    ('SLUS-01205', 'Kengo'),
]

for serial, title in games:
    # Search by title
    query = f'{title} playstation'
    url = f'https://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&fl[]=title&rows=10&output=json'
    try:
        r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            data = r.json()
            docs = data.get('response', {}).get('docs', [])
            print(f'\n{serial} ({title}): {len(docs)} results')
            for d in docs[:3]:
                identifier = d['identifier']
                # Check if item has bin/cue files
                url2 = f'https://archive.org/metadata/{identifier}'
                r2 = requests.get(url2, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
                if r2.status_code == 200:
                    data2 = r2.json()
                    files = data2.get('files', [])
                    bin_files = [f for f in files if f.get('name', '').lower().endswith('.bin')]
                    cue_files = [f for f in files if f.get('name', '').lower().endswith('.cue')]
                    chd_files = [f for f in files if f.get('name', '').lower().endswith('.chd')]
                    if bin_files or cue_files or chd_files:
                        # Check if downloadable
                        if cue_files:
                            test_file = cue_files[0]['name']
                        elif bin_files:
                            test_file = bin_files[0]['name']
                        elif chd_files:
                            test_file = chd_files[0]['name']
                        else:
                            continue

                        test_url = f'https://archive.org/download/{identifier}/{quote(test_file)}'
                        r_head = requests.head(test_url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True)
                        status = r_head.status_code
                        size = r_head.headers.get('content-length', '?')
                        print(f'  {identifier}: {len(bin_files)} bin, {len(cue_files)} cue, {len(chd_files)} chd | HEAD={status} size={size}')
                        if status == 200:
                            print(f'    DOWNLOADABLE! {test_url[:80]}')
    except Exception as e:
        print(f'  Error: {e}')
