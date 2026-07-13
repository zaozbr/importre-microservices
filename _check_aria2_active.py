"""Verifica todos os downloads ativos no aria2c via RPC."""
import json, urllib.request

payload = json.dumps({"jsonrpc":"2.0","id":"1","method":"aria2.tellActive","params":["token:psx_download_2026",["gid","status","totalLength","completedLength","downloadSpeed","connections","files","errorCode","errorMessage"]]}).encode()
req = urllib.request.Request("http://localhost:6801/jsonrpc", data=payload, headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req, timeout=10) as r:
    result = json.loads(r.read())

active = result.get("result", [])
print(f"Downloads ativos: {len(active)}")
total_speed = 0
stuck = []
for d in active:
    gid = d.get("gid","?")
    total = int(d.get("totalLength",0))
    completed = int(d.get("completedLength",0))
    speed = int(d.get("downloadSpeed",0))
    conns = int(d.get("connections",0))
    total_speed += speed
    files = d.get("files",[])
    fname = files[0].get("path","") if files else ""
    # Extrair serial do nome do arquivo
    serial = fname.split("_")[0] if fname else "?"
    status = d.get("status","?")
    err = d.get("errorMessage","")
    
    speed_mb = speed / 1024 / 1024
    comp_mb = completed / 1024 / 1024
    total_mb = total / 1024 / 1024
    
    marker = ""
    if total == 0 and completed == 0:
        marker = " [STUCK 0/0]"
        stuck.append(gid)
    elif speed == 0:
        marker = " [SPEED=0]"
    elif speed < 1024*1024:
        marker = f" [SLOW {speed_mb:.2f}MB/s]"
    
    print(f"  {serial:15s} {comp_mb:7.1f}/{total_mb:7.1f}MB {speed_mb:5.2f}MB/s c={conns:2d} {status}{marker} err={err}")

print(f"\nVelocidade total: {total_speed/1024/1024:.2f}MB/s")
print(f"Stuck (0/0): {len(stuck)}")

# Tell waiting
payload2 = json.dumps({"jsonrpc":"2.0","id":"2","method":"aria2.tellWaiting","params":["token:psx_download_2026",0,50,["gid","status","totalLength"]]}).encode()
req2 = urllib.request.Request("http://localhost:6801/jsonrpc", data=payload2, headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req2, timeout=10) as r2:
    result2 = json.loads(r2.read())
waiting = result2.get("result", [])
print(f"Waiting: {len(waiting)}")

# Tell stopped
payload3 = json.dumps({"jsonrpc":"2.0","id":"3","method":"aria2.tellStopped","params":["token:psx_download_2026",0,50,["gid","status","totalLength","completedLength","errorCode"]]}).encode()
req3 = urllib.request.Request("http://localhost:6801/jsonrpc", data=payload3, headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req3, timeout=10) as r3:
    result3 = json.loads(r3.read())
stopped = result3.get("result", [])
print(f"Stopped: {len(stopped)}")
for s in stopped[-5:]:
    status = s.get("status","?")
    err = s.get("errorCode","0")
    total = int(s.get("totalLength",0))
    comp = int(s.get("completedLength",0))
    print(f"  stopped: {s.get('gid','?')[:12]} status={status} {comp/1024/1024:.1f}/{total/1024/1024:.1f}MB err={err}")
