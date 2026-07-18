import json

d = json.load(open(r'F:\importre_state\download_progress_v6.json', 'r', encoding='utf-8'))
cache = json.load(open(r'F:\importre_state\vimm_cache_v2.json', 'r', encoding='utf-8'))

# Remove demo cache entries so they can be searched fresh
demo_serials = ['SLUS-00510', 'SLES-01344', 'SLES-00532']
for s in demo_serials:
    if s in cache:
        del cache[s]
        print(f'Removed {s} from cache (demo)')
    if s in d.get('failed', {}):
        del d['failed'][s]

# Clear all failed entries for retry
failed_count = len(d.get('failed', {}))
d['failed'] = {}
print(f'Cleared {failed_count} failed entries')

with open(r'F:\importre_state\download_progress_v6.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
with open(r'F:\importre_state\vimm_cache_v2.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, indent=2, ensure_ascii=False)

print(f'Final: Completed={len(d.get("completed",{}))}, Failed=0')
