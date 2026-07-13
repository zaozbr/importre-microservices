"""Verifica falhas no queue."""
import json
q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
print(f"pending={len(q.get('queue',[]))} ip={len(q.get('in_progress',{}))} done={len(q.get('completed',{}))} fail={len(q.get('failed',{}))}")
failed = q.get("failed", {})
if isinstance(failed, dict):
    for k, v in list(failed.items())[:10]:
        err = v.get("error", "") if isinstance(v, dict) else str(v)
        print(f"  FAIL: {k} - {err[:100]}")
elif isinstance(failed, list):
    for item in failed[:10]:
        if isinstance(item, dict):
            print(f"  FAIL: {item.get('serial','')} - {item.get('error','')[:100]}")
