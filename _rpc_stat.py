import urllib.request, json, sys

req = urllib.request.Request(
    "http://127.0.0.1:6801/jsonrpc",
    data=json.dumps({"jsonrpc": "2.0", "id": "1", "method": "aria2.getGlobalStat", "params": ["token:psx_download_2026"]}).encode(),
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
    print(f"ERRO: {e}")
    sys.exit(1)
