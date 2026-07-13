import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _aria2_manager

mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
print(f"running: {mgr.is_daemon_running()}")

# Tentar com timeout maior
import urllib.request
req = urllib.request.Request(
    "http://127.0.0.1:6801/jsonrpc",
    data=json.dumps({"jsonrpc": "2.0", "id": "1", "method": "aria2.getGlobalStat", "params": ["psx_download_2026"]}).encode(),
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        result = data.get("result", {})
        speed = int(result.get("downloadSpeed", 0))
        print(f"speed: {speed/1024/1024:.2f}MB/s")
        print(f"active: {result.get('numActive')}")
        print(f"waiting: {result.get('numWaiting')}")
        print(f"stopped: {result.get('numStopped')}")
except Exception as e:
    print(f"RPC erro: {e}")

# Verificar ativos
try:
    active = mgr.tell_active()
    print(f"\nAtivos: {len(active)}")
    for d in active[:5]:
        speed = int(d.get("downloadSpeed", 0))
        comp = int(d.get("completedLength", 0))
        total = int(d.get("totalLength", 0))
        status = d.get("status")
        files = d.get("files", [])
        url = files[0]["uris"][0]["uri"] if files and files[0].get("uris") else "?"
        print(f"  {status} {speed/1024/1024:.2f}MB/s {comp/1024/1024:.0f}/{total/1024/1024:.0f}MB {url[:60]}")
except Exception as e:
    print(f"tell_active erro: {e}")
