"""Verifica TODAS as falhas com detalhes."""
import json
q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
failed = q.get("failed", {})
if isinstance(failed, dict):
    items = list(failed.items())
elif isinstance(failed, list):
    items = [(item.get("serial",""), item) for item in failed if isinstance(item, dict)]
else:
    items = []

# Categorizar falhas por prefixo
prefixes = {}
for serial, v in items:
    prefix = serial.split("-")[0] if "-" in serial else serial[:6]
    prefixes[prefix] = prefixes.get(prefix, 0) + 1
print(f"Total falhas: {len(items)}")
print("Por prefixo:")
for p, c in sorted(prefixes.items(), key=lambda x: -x[1]):
    print(f"  {p}: {c}")

# Mostrar falhas não-HBREW
print("\nFalhas não-HBREW:")
for serial, v in items:
    if not serial.startswith("HBREW"):
        err = v.get("error", "") if isinstance(v, dict) else str(v)
        retry = v.get("retry_count", 0) if isinstance(v, dict) else 0
        print(f"  {serial}: retry={retry} err={err[:100]}")
