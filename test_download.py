import subprocess, os, time

pluto_url = 'https://pluto.romulation.net/files/guest/eyJpdiI6Iitha1cxRnYxeHMyM2krV1pKTE82RXc9PSIsInZhbHVlIjoiWFJKMmJuclFadWlxaTZZamg5dURIam55OTN1YUJNQmV6MFVIQnlML3NZbFV5SUZ0VUpTdEJrem1WZk5KVXloWiIsIm1hYyI6IjQ5ZWYxODkyNmFmZDEyM2ViYTEwYTM1MjdhNDEzYmVjZjFjYTdlNDE4MGExNGUyOGUyMDc2NmVlMjY2NGFmNjUiLCJ0YWciOiIifQ==/'
dest = r'F:\downloads\psx_faltantes\SLUS-00510.rar'

cmd = ['curl', '-L', '-o', dest, '--connect-timeout', '30', '--max-time', '120',
       '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
       '-H', 'Referer: https://www.romulation.org/rom/PSX/Vigilante-8',
       '-s', '--show-error', pluto_url]

t0 = time.time()
result = subprocess.run(cmd, capture_output=True, text=True, timeout=150)
dt = time.time() - t0
print(f'rc={result.returncode}, time={dt:.1f}s, stderr={result.stderr[:200]}')
if os.path.exists(dest):
    size = os.path.getsize(dest)
    print(f'file size: {size} bytes')
    if size < 1024:
        with open(dest, 'r', errors='ignore') as f:
            print('content:', f.read()[:300])
else:
    print('file not created')
