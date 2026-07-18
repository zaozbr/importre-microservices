import json

d = json.load(open(r'F:\importre_state\download_progress_v6.json', 'r', encoding='utf-8'))
# Clear all failed entries so they can be retried
failed_count = len(d.get('failed', {}))
d['failed'] = {}
print(f'Cleared {failed_count} failed entries for retry')

with open(r'F:\importre_state\download_progress_v6.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
print(f'Remaining: Completed={len(d.get("completed",{}))}')
