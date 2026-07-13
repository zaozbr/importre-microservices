"""Remove downloads stuck em 0/0 do aria2c."""
import json, urllib.request

# Listar ativos
payload = json.dumps({"jsonrpc":"2.0","id":"1","method":"aria2.tellActive","params":["token:psx_download_2026",["gid","totalLength","completedLength","downloadSpeed","files"]]}).encode()
req = urllib.request.Request("http://localhost:6801/jsonrpc", data=payload, headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req, timeout=10) as r:
    result = json.loads(r.read())

active = result.get("result", [])
removed = 0
for d in active:
    gid = d.get("gid","")
    total = int(d.get("totalLength",0))
    completed = int(d.get("completedLength",0))
    speed = int(d.get("downloadSpeed",0))
    
    # Stuck: 0 bytes totais e 0 speed
    if total == 0 and completed == 0 and speed == 0:
        # Remover
        payload2 = json.dumps({"jsonrpc":"2.0","id":"rm","method":"aria2.forceRemove","params":["token:psx_download_2026",gid]}).encode()
        req2 = urllib.request.Request("http://localhost:6801/jsonrpc", data=payload2, headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req2, timeout=5) as r2:
                json.loads(r2.read())
            removed += 1
            print(f"Removido stuck: {gid}")
        except Exception as e:
            print(f"Erro removendo {gid}: {e}")

print(f"Total removidos: {removed}")
