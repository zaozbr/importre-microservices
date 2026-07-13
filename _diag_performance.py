"""Diagnóstico de performance: por que estamos a 0.5MB/s e não 20MB/s?"""
import sys, json, time, subprocess
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _aria2_manager import Aria2Manager

m = Aria2Manager()
print(f"Daemon rodando: {m.is_daemon_running()}")

# 1. Status global
stat = m.get_global_stat()
print(f"\n=== STATUS GLOBAL ===")
print(f"Active: {stat.get('active', 0)}")
print(f"Waiting: {stat.get('waiting', 0)}")
print(f"Stopped: {stat.get('stopped', 0)}")
print(f"Download speed: {int(stat.get('downloadSpeed', 0)) / 1e6:.2f} MB/s")

# 2. Detalhes de cada download ativo
print(f"\n=== DOWNLOADS ATIVOS ===")
active = m.tell_active()
for d in active:
    gid = d.get("gid")
    total = int(d.get("totalLength", 0))
    completed = int(d.get("completedLength", 0))
    speed = int(d.get("downloadSpeed", 0))
    conns = int(d.get("connections", 0))
    files = d.get("files", [{}])
    path = files[0].get("path", "") if files else ""
    url = files[0].get("uris", [{}])[0].get("uri", "") if files and files[0].get("uris") else ""
    pct = (completed / total * 100) if total > 0 else 0
    print(f"\n  GID={gid}")
    print(f"    file: {path}")
    print(f"    url: {url[:80]}")
    print(f"    progress: {completed/1e6:.1f}/{total/1e6:.1f}MB ({pct:.1f}%)")
    print(f"    speed: {speed/1e6:.2f} MB/s")
    print(f"    connections: {conns}")
    print(f"    status: {d.get('status')}")

# 3. Downloads waiting (na fila do aria2c)
print(f"\n=== DOWNLOADS NA FILA (waiting) ===")
waiting = m.tell_waiting(0, 50)
print(f"Total waiting: {len(waiting)}")
for d in waiting[:5]:
    files = d.get("files", [{}])
    path = files[0].get("path", "") if files else ""
    print(f"  {d.get('gid')}: {path} status={d.get('status')}")

# 4. Config atual do aria2c
print(f"\n=== CONFIG ARIA2C ===")
# Verificar opções globais
try:
    opts = m._call("aria2.getGlobalOption", [])
    relevant = {k: v for k, v in opts.items() if k in [
        "max-concurrent-downloads", "max-connection-per-server", "split",
        "min-split-size", "max-overall-download-limit", "max-download-limit",
        "retry-wait", "max-tries", "connect-timeout", "timeout",
    ]}
    for k, v in sorted(relevant.items()):
        print(f"  {k}: {v}")
except Exception as e:
    print(f"  Erro ao obter config: {e}")

# 5. Teste de velocidade direta (curl) vs aria2c
print(f"\n=== TESTE DE VELOCIDADE (curl direto) ===")
import urllib.request
# Testar latência e velocidade do archive.org
test_url = "https://archive.org/download/psx-ntscj-chd-zstd/ntscj/NOeL%203%20-%20Mission%20on%20the%20Line%20%28Japan%29%20%28Disc%201%29%20%28Major%20Wave%29.chd"
try:
    req = urllib.request.Request(test_url, headers={"Range": "bytes=0-10485759"})  # 10MB
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    elapsed = time.time() - t0
    speed = len(data) / elapsed / 1e6
    print(f"  curl 10MB do archive.org: {elapsed:.1f}s = {speed:.2f} MB/s")
except Exception as e:
    print(f"  curl erro: {e}")

# 6. Verificar banda total da rede
print(f"\n=== BANDA DE REDE ===")
try:
    result = subprocess.run(
        ['powershell', '-Command',
         "Get-Counter '\\Network Interface(*)\\Bytes Total/sec' | Select-Object -ExpandProperty CounterSamples | Where-Object {$_.CookedValue -gt 0} | Sort-Object CookedValue -Descending | Select-Object -First 3 | Format-Table InstanceName, CookedValue -AutoSize"],
        capture_output=True, text=True, timeout=10)
    print(result.stdout.strip())
except:
    pass
