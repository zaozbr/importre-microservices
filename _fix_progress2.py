import json
with open(r'F:\importre_state\download_progress_v6.json', 'r', encoding='utf-8') as f:
    progress = json.load(f)
for s in ['SLES-00532']:
    if s in progress.get('completed', {}):
        del progress['completed'][s]
        print(f'Removed {s} from completed')
with open(r'F:\importre_state\download_progress_v6.json', 'w', encoding='utf-8') as f:
    json.dump(progress, f, indent=2, ensure_ascii=False)

with open(r'F:\importre_state\vimm_cache_v2.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)
for s in ['SLES-00532']:
    if s in cache:
        del cache[s]
        print(f'Removed {s} from cache')
with open(r'F:\importre_state\vimm_cache_v2.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, indent=2, ensure_ascii=False)
print('Done')
