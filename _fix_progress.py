import json

# Fix progress file - remove bad entries
with open(r'F:\importre_state\download_progress_v6.json', 'r', encoding='utf-8') as f:
    progress = json.load(f)

# Remove entries that were demos or wrong games
to_remove = ['SLUS-00510', 'SLES-00532', 'SLES-00714']
for serial in to_remove:
    if serial in progress.get('completed', {}):
        del progress['completed'][serial]
        print(f'Removed {serial} from completed')
    if serial in progress.get('failed', {}):
        del progress['failed'][serial]
        print(f'Removed {serial} from failed')

with open(r'F:\importre_state\download_progress_v6.json', 'w', encoding='utf-8') as f:
    json.dump(progress, f, indent=2, ensure_ascii=False)

# Fix vimm cache - remove bad entries
with open(r'F:\importre_state\vimm_cache_v2.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

for serial in to_remove:
    if serial in cache:
        del cache[serial]
        print(f'Removed {serial} from vimm cache')

with open(r'F:\importre_state\vimm_cache_v2.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, indent=2, ensure_ascii=False)

print('Done fixing progress and cache')
