import psutil

print("=== TODOS PROCESSOS PYTHON >50MB ===")
for p in psutil.process_iter(['pid','name','cmdline','memory_info']):
    try:
        mi = p.info['memory_info']
        rss_mb = mi.rss / 1024 / 1024 if mi else 0
        name = p.info['name'] or ''
        cmd = ' '.join(p.info['cmdline'] or [])[:150]
        if rss_mb > 50 and 'python' in name.lower():
            print(f"{rss_mb:8.0f}MB  PID={p.info['pid']:6d}  {name}  {cmd}")
    except: pass

print("\n=== PROCESSOS CHROMIUM/CHROME (Playwright) ===")
chrome_total = 0
chrome_count = 0
for p in psutil.process_iter(['pid','name','cmdline','memory_info']):
    try:
        mi = p.info['memory_info']
        rss_mb = mi.rss / 1024 / 1024 if mi else 0
        name = p.info['name'] or ''
        cmd = ' '.join(p.info['cmdline'] or [])[:100]
        if 'chromium' in name.lower() or ('chrome' in name.lower() and 'playwright' in cmd.lower()):
            chrome_total += rss_mb
            chrome_count += 1
            if rss_mb > 50:
                print(f"{rss_mb:8.0f}MB  PID={p.info['pid']:6d}  {cmd}")
    except: pass
print(f"\nTotal chromium: {chrome_count} processos, {chrome_total/1024:.1f}GB")

print("\n=== TODOS CHROME.EXE ===")
all_chrome = 0
all_chrome_count = 0
for p in psutil.process_iter(['pid','name','memory_info']):
    try:
        mi = p.info['memory_info']
        rss_mb = mi.rss / 1024 / 1024 if mi else 0
        name = p.info['name'] or ''
        if 'chrome' in name.lower():
            all_chrome += rss_mb
            all_chrome_count += 1
    except: pass
print(f"Total chrome.exe: {all_chrome_count} processos, {all_chrome/1024:.1f}GB")

print("\n=== MEMORIA TOTAL DO SISTEMA ===")
vm = psutil.virtual_memory()
print(f"Total: {vm.total/1024/1024/1024:.1f}GB  Usada: {vm.used/1024/1024/1024:.1f}GB  Livre: {vm.available/1024/1024/1024:.1f}GB  ({vm.percent}%)")

print("\n=== IMPORTRE_SERVER DUPLICADOS ===")
srv_count = 0
for p in psutil.process_iter(['pid','cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'importre_server' in cmd:
            srv_count += 1
            print(f"  PID={p.info['pid']}")
    except: pass
print(f"Total importre_server: {srv_count}")
