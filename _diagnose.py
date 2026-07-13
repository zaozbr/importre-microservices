"""Diagnostico completo do estado do importre."""
import json, urllib.request, sys, os, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 1. Status da API
r = urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=5)
data = json.loads(r.read())
s = data['status']

print('=== STATUS IMPORTRE ===')
print(f'pending={s["pending"]} in_progress={s["in_progress"]} completed={s["completed"]} failed={s["failed"]}')
print(f'phases: searching={s["searching"]} starting={s["starting"]} downloading={s["downloading"]} verifying={s["verifying"]}')
print(f'buffer_ready={s.get("buffer_ready",0)}')
print()

dl = s.get('dl_progress', {})
print(f'dl_progress items: {len(dl)}')
total_speed = 0
for serial, p in dl.items():
    spd = p.get('speed', 0)
    total_speed += spd
    dl_mb = p.get('downloaded', 0) / 1e6
    tot_mb = p.get('total', 0) / 1e6
    spd_mb = spd / 1e6
    pct = (dl_mb / tot_mb * 100) if tot_mb > 0 else 0
    print(f'  {serial}: {dl_mb:.1f}/{tot_mb:.1f}MB ({pct:.0f}%) speed={spd_mb:.2f}MB/s')
print(f'  VELOCIDADE TOTAL: {total_speed/1e6:.2f} MB/s')
print()

busy = s.get('busy_sites', {})
print('busy_sites:', json.dumps(busy, indent=2))
print()

# 2. Processos
import subprocess
print('=== PROCESSOS PYTHON ===')
result = subprocess.run(['wmic', 'process', 'where', "name='python.exe' or name='pythonw.exe'", 'get', 'ProcessId,CommandLine', '/format:list'], capture_output=True, text=True, timeout=10)
for line in result.stdout.split('\n'):
    line = line.strip()
    if line and ('importre' in line.lower() or 'chd' in line.lower() or 'supervisor' in line.lower()):
        print(f'  {line}')
print()

# 3. CHD temp
chd_temp = r'F:\chd_temp'
if os.path.exists(chd_temp):
    chds = [f for f in os.listdir(chd_temp) if f.endswith('.chd')]
    print(f'=== CHD TEMP ({chd_temp}) ===')
    print(f'  CHDs: {len(chds)}')
    for f in chds[:10]:
        sz = os.path.getsize(os.path.join(chd_temp, f)) / 1e6
        print(f'  {f}: {sz:.1f}MB')
    if len(chds) > 10:
        print(f'  ... e mais {len(chds)-10}')
print()

# 4. Espaco em disco
import shutil
for drive in ['C:', 'D:', 'F:']:
    try:
        usage = shutil.disk_usage(drive + '\\')
        free_gb = usage.free / 1e9
        total_gb = usage.total / 1e9
        pct = (usage.used / usage.total) * 100
        print(f'  {drive} {free_gb:.1f}GB livre / {total_gb:.1f}GB total ({pct:.0f}% usado)')
    except:
        pass
