import json, os

d = json.load(open(r'F:\importre_state\download_progress_v6.json', 'r', encoding='utf-8'))

# Remove SLES-00532 (demo) from completed
if 'SLES-00532' in d.get('completed', {}):
    del d['completed']['SLES-00532']
    print('Removed SLES-00532 (demo) from completed')

# Check which CHDs exist but are not in completed
chd_dir = r'F:\testes'
chd_files = [f for f in os.listdir(chd_dir) if f.endswith('.chd')]
print(f'\nCHD files in testes: {len(chd_files)}')

# Map serial from CHD filename
import re
for chd in sorted(chd_files):
    # Extract serial from filename (last part before .chd)
    m = re.search(r'-(SL[A-Z]+-\d+|SC[A-Z]+-\d+|SI[A-Z]+-\d+)\.chd$', chd)
    if m:
        serial = m.group(1)
        in_completed = serial in d.get('completed', {})
        in_failed = serial in d.get('failed', {})
        status = 'OK' if in_completed else ('FAILED' if in_failed else 'NOT_IN_PROGRESS')
        if not in_completed:
            print(f'  {chd} -> {serial}: {status}')
            # Add to completed
            d.setdefault('completed', {})[serial] = {
                'name': chd.replace(f'-{serial}.chd', '').replace('-', ' '),
                'source': 'vimm_chd_exists',
                'region': 'unknown'
            }
            # Remove from failed if present
            if serial in d.get('failed', {}):
                del d['failed'][serial]

# Also remove SLUS-00510 from failed (demo cache issue)
if 'SLUS-00510' in d.get('failed', {}):
    del d['failed']['SLUS-00510']
    print('Removed SLUS-00510 from failed (will retry)')

# Remove from cache too
cache = json.load(open(r'F:\importre_state\vimm_cache_v2.json', 'r', encoding='utf-8'))
if 'SLUS-00510' in cache:
    del cache['SLUS-00510']
    print('Removed SLUS-00510 from cache')
if 'SLES-00532' in cache:
    del cache['SLES-00532']
    print('Removed SLES-00532 from cache')

with open(r'F:\importre_state\download_progress_v6.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
with open(r'F:\importre_state\vimm_cache_v2.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, indent=2, ensure_ascii=False)

print(f'\nFinal: Completed={len(d.get("completed",{}))}, Failed={len(d.get("failed",{}))}')
