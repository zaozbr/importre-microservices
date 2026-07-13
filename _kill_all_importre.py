"""Mata todos os processos do importre (supervisor, server, workers)."""
import psutil

killed = 0
for p in psutil.process_iter(['pid', 'cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'importre' in cmd and 'psutil' not in cmd and '_kill_all' not in cmd:
            p.kill()
            killed += 1
            print(f"Kill {p.info['pid']}: {cmd[:80]}")
    except Exception:
        pass
print(f"Total killed: {killed}")
