import json
path = r'D:\roms\library\roms\_importre_state\dl_progress.json'
try:
    with open(path, 'r') as f:
        data = json.load(f)
except Exception:
    data = {}
print('downloads ativos:', len(data))
for serial, info in list(data.items())[:20]:
    site = info.get('site', '?')
    pct = info.get('percent', 0)
    speed = info.get('speed_mbps', 0)
    dl = info.get('downloaded', 0) // 1024
    total = info.get('total', 0) // 1024
    print(f'{serial}: {site} {pct:.1f}% {speed:.2f} MB/s {dl}KB/{total}KB')
