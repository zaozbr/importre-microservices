import requests, json
r = requests.get('http://127.0.0.1:8765/api/status', timeout=5)
d = r.json()
s = d.get('status', d)
print(f"Server: {d.get('server', '?')}")
print(f"Completed: {s.get('completed', 0)}")
print(f"Failed: {s.get('failed', 0)}")
print(f"Pending: {s.get('pending', 0)}")
print(f"In Progress: {s.get('in_progress_items', 0)}")
print(f"Total: {s.get('total', 0)}")
# Verificar CHD
try:
    r2 = requests.get('http://127.0.0.1:8766/api/collection', timeout=5)
    c = r2.json()
    print(f"\nCHD Converter:")
    print(f"  Total: {c.get('total', 0)}")
    print(f"  CHD: {c.get('chd_count', 0)}")
    print(f"  BIN: {c.get('bin_count', 0)}")
    print(f"  Pending: {c.get('pending_chd', 0)}")
    print(f"  Converting: {c.get('converting', 0)}")
    print(f"  Size: {c.get('total_size_gb', 0):.1f} GB")
except Exception as e:
    print(f"\nCHD Converter: offline ({e})")
