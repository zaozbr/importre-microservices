import json, os, re

# Build progress from scratch based on actual CHD files
chd_dir = r'F:\testes'
chd_files = [f for f in os.listdir(chd_dir) if f.endswith('.chd')]

completed = {}
for chd in chd_files:
    m = re.search(r'-(SL[A-Z]+-\d+|SC[A-Z]+-\d+|SI[A-Z]+-\d+)\.chd$', chd)
    if m:
        serial = m.group(1)
        name = chd.replace(f'-{serial}.chd', '').replace('-', ' ')
        completed[serial] = {
            'name': name,
            'source': 'vimm',
            'region': 'unknown'
        }

# Remove SLES-00532 if it exists (demo)
if 'SLES-00532' in completed:
    del completed['SLES-00532']
    # Also delete the CHD file
    chd_path = os.path.join(chd_dir, 'Command-Conquer-Der-Tiberiumkonflikt-SLES-00532.chd')
    if os.path.exists(chd_path):
        os.remove(chd_path)
        print(f'Deleted demo CHD: {chd_path}')

progress = {
    'completed': completed,
    'failed': {},
    'skipped': {}
}

with open(r'F:\importre_state\download_progress_v6.json', 'w', encoding='utf-8') as f:
    json.dump(progress, f, indent=2, ensure_ascii=False)

print(f'Progress rebuilt: {len(completed)} completed, 0 failed')
for k, v in sorted(completed.items()):
    print(f'  {k}: {v["name"]}')
