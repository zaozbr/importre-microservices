import psutil
for p in psutil.process_iter(['pid','name','cmdline','memory_info']):
    try:
        mi = p.info['memory_info']
        rss_mb = mi.rss / 1024 / 1024 if mi else 0
        cmd = ' '.join(p.info['cmdline'] or [])[:120]
        if 'importre' in cmd and rss_mb > 30:
            print(f"{rss_mb:8.0f}MB  PID={p.info['pid']:6d}  {cmd}")
    except: pass
