import json, os

d = json.load(open(r'F:\importre_state\download_progress_v6.json', 'r', encoding='utf-8'))
cache = json.load(open(r'F:\importre_state\vimm_cache_v2.json', 'r', encoding='utf-8'))

# Remove SLES-00532 from completed (CHD was deleted, need to re-download)
if 'SLES-00532' in d.get('completed', {}):
    del d['completed']['SLES-00532']
    print('Removed SLES-00532 from completed (need re-download)')

# Remove SLES-00532 from cache (had demo entry)
if 'SLES-00532' in cache:
    del cache['SLES-00532']
    print('Removed SLES-00532 from cache')

# Remove Ehrgeiz from cache (had demo entry) - will search fresh
if 'SCPS-45364' in cache:
    del cache['SCPS-45364']
    print('Removed SCPS-45364 (Ehrgeiz) from cache - will search fresh')

# Clear all failed entries for retry
failed_count = len(d.get('failed', {}))
d['failed'] = {}
print(f'Cleared {failed_count} failed entries')

# Add HBREW games that have CHDs but aren't in progress
chd_dir = r'F:\testes'
import re
for f in os.listdir(chd_dir):
    if f.endswith('.chd'):
        m = re.search(r'-(HBREW-\d+)\.chd$', f)
        if m:
            serial = m.group(1)
            if serial not in d.get('completed', {}):
                d['completed'][serial] = {
                    'name': f.replace(f'-{serial}.chd', '').replace('-', ' '),
                    'source': 'chd_exists',
                    'region': 'HBREW'
                }
                print(f'Added {serial} to completed (CHD exists)')

with open(r'F:\importre_state\download_progress_v6.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
with open(r'F:\importre_state\vimm_cache_v2.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, indent=2, ensure_ascii=False)

print(f'\nFinal: Completed={len(d.get("completed",{}))}, Failed=0')
