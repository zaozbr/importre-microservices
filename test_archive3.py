import requests, json
from urllib.parse import quote

serials = ['SLUS-00510', 'SLUS-01095', 'SLES-01875', 'SLUS-00640', 'SLES-00327']

for serial in serials:
    query = f'"{serial}"'
    url = f'https://archive.org/advancedsearch.php?q={quote(query)}&fl[]=identifier&fl[]=title&rows=5&output=json'
    r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    data = r.json()
    docs = data.get('response', {}).get('docs', [])
    print(f'\n{serial}: {len(docs)} results')
    for d in docs[:3]:
        identifier = d['identifier']
        # Get files
        url2 = f'https://archive.org/metadata/{identifier}'
        r2 = requests.get(url2, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        data2 = r2.json()
        files = data2.get('files', [])
        chd_files = [f for f in files if f.get('name', '').lower().endswith('.chd')]
        archive_files = [f for f in files if any(f.get('name', '').lower().endswith(ext) for ext in ['.7z', '.zip', '.rar'])]
        cue_files = [f for f in files if f.get('name', '').lower().endswith('.cue')]
        iso_files = [f for f in files if f.get('name', '').lower().endswith('.iso')]
        bin_files = [f for f in files if f.get('name', '').lower().endswith('.bin')]

        print(f'  {identifier} -> {d.get("title","")[:50]}')
        if chd_files:
            print(f'    CHD: {chd_files[0]["name"]} ({int(chd_files[0].get("size",0))/1024/1024:.1f} MB)')
        if archive_files:
            print(f'    Archive: {archive_files[0]["name"]}')
        if cue_files:
            print(f'    CUE: {cue_files[0]["name"]}')
        if iso_files:
            print(f'    ISO: {iso_files[0]["name"]}')
        if bin_files:
            print(f'    BIN: {bin_files[0]["name"]}')
