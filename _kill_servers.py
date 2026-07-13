import psutil
killed = 0
for p in psutil.process_iter(['pid', 'cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'importre_server' in cmd:
            p.kill()
            killed += 1
    except:
        pass
print(f'Mortos: {killed} importre_server')
