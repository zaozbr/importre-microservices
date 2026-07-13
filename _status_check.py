import urllib.request, json
r = urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=10)
d = json.loads(r.read().decode())
s = d.get('status', {})
print(f"pending={s.get('pending',0)} ip={s.get('in_progress',0)} dl={s.get('downloading',0)} ok={s.get('completed',0)} fail={s.get('failed',0)}")
dl = s.get('dl_progress', {})
print(f"downloads ativos: {len(dl)}")
total_speed = 0
for k, v in dl.items():
    speed = v.get('speed', 0) / 1e6
    total_speed += speed
    dl_mb = v.get('downloaded', 0) / 1e6
    print(f"  {k}: {speed:.1f}MB/s {dl_mb:.1f}MB")
print(f"velocidade total: {total_speed:.1f}MB/s")
