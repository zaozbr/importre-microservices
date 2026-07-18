import json
# Clear bad cache entries (demos and rate-limited)
with open(r'F:\importre_state\vimm_cache_v2.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

# Remove Vigilante 8 cache (it has a demo vault_id)
to_clean = ['SLUS-00510']
for s in to_clean:
    if s in cache:
        del cache[s]
        print(f'Removed {s} from cache')
    # Also remove from failed in progress
with open(r'F:\importre_state\download_progress_v6.json', 'r', encoding='utf-8') as f:
    progress = json.load(f)
for s in to_clean:
    if s in progress.get('failed', {}):
        del progress['failed'][s]
        print(f'Removed {s} from failed')

with open(r'F:\importre_state\vimm_cache_v2.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, indent=2, ensure_ascii=False)
with open(r'F:\importre_state\download_progress_v6.json', 'w', encoding='utf-8') as f:
    json.dump(progress, f, indent=2, ensure_ascii=False)
print('Done')
