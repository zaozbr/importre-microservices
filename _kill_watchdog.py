import psutil
for p in psutil.process_iter(['pid', 'cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'watchdog' in cmd.lower() and 'importre' in cmd.lower():
            print('Killing watchdog PID', p.info['pid'])
            p.kill()
    except:
        pass
print('Done')
