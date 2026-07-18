import json
d = json.load(open(r'F:\importre_state\download_progress_v6.json', 'r', encoding='utf-8'))
print(f'Completed: {len(d.get("completed",{}))}')
print(f'Failed: {len(d.get("failed",{}))}')
print(f'Skipped: {len(d.get("skipped",{}))}')
print('\nCompleted games:')
for k, v in d.get('completed', {}).items():
    print(f'  {k}: {v["name"]} [{v.get("region","")}] via {v.get("source","")}')
