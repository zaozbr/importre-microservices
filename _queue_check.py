import json
q = json.load(open(r'D:\roms\library\roms\_importre_state\queue.json', 'r', encoding='utf-8'))
print(f"pending={len(q.get('queue',[]))} ip={len(q.get('in_progress',{}))} done={len(q.get('completed',[]))} fail={len(q.get('failed',{}))}")
ip = q.get('in_progress', {})
for k, v in list(ip.items())[:5]:
    print(f"  {k}: phase={v.get('_phase','?')} site={v.get('_current_site','?')}")
