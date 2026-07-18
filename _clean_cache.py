import json
cache = json.load(open(r'F:\importre_state\vimm_cache_v2.json', 'r', encoding='utf-8'))
# Remove entries for games that are already completed or need fresh search
to_remove = ['SLUS-00510', 'SLES-00532', 'SLES-00714', 'SLES-03990']
for s in to_remove:
    if s in cache:
        del cache[s]
        print(f'Removed {s} from cache')
with open(r'F:\importre_state\vimm_cache_v2.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, indent=2, ensure_ascii=False)
print(f'Cache now has {len(cache)} entries')
