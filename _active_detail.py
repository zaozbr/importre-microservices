"""Verifica downloads ativos no aria2c com detalhes."""
import urllib.request, json

req = urllib.request.Request(
    "http://127.0.0.1:6801/jsonrpc",
    data=json.dumps({"jsonrpc": "2.0", "id": "1", "method": "aria2.tellActive", "params": ["token:psx_download_2026", []]}).encode(),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read())
    active = data.get("result", [])

print(f"Downloads ativos: {len(active)}")
total_speed = 0
for d in active[:15]:
    speed = int(d.get("downloadSpeed", 0))
    total_speed += speed
    comp = int(d.get("completedLength", 0))
    total = int(d.get("totalLength", 0))
    files = d.get("files", [])
    url = files[0]["uris"][0]["uri"] if files and files[0].get("uris") else "?"
    fonte = "coolrom" if "coolrom" in url else ("archive" if "archive" in url else "other")
    pct = (comp/total*100) if total > 0 else 0
    print(f"  [{fonte}] {speed/1024/1024:.2f}MB/s {pct:.0f}% ({comp/1024/1024:.0f}/{total/1024/1024:.0f}MB) {url[:60]}")

print(f"\nVelocidade total: {total_speed/1024/1024:.2f}MB/s")

# Contar por fonte
fontes = {}
for d in active:
    files = d.get("files", [])
    url = files[0]["uris"][0]["uri"] if files and files[0].get("uris") else "?"
    fonte = "coolrom" if "coolrom" in url else ("archive" if "archive" in url else "other")
    fontes[fonte] = fontes.get(fonte, 0) + 1
print(f"Por fonte: {fontes}")
