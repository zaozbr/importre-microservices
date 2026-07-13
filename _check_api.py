import requests, json
r = requests.get('http://127.0.0.1:8765/api/status', timeout=5)
d = r.json()
print(f"State: {d['process_state']}")
print(f"Pending: {d['status']['pending']}")
print(f"In Progress: {d['status']['in_progress']}")
print(f"Completed: {d['status']['completed']}")
print(f"Failed: {d['status']['failed']}")
ip = d['status']['in_progress_items']
for k, v in ip.items():
    print(f"  {k}: phase={v.get('_phase')} site={v.get('_current_site')} detail={v.get('_detail')}")
