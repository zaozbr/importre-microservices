"""Verifica overlap entre coolrom_cache e pending JP.
O cache tem 2941 entradas — quantas são JP e quantas batem com pending?
"""
import json
import os
import re

STATE = r"D:\roms\library\roms\_importre_state"

# Carregar caches
coolrom_cache = json.load(open(os.path.join(STATE, "coolrom_cache.json"), "r", encoding="utf-8"))
print(f"Coolrom cache: {len(coolrom_cache)} entradas")

# Verificar formato das chaves do cache
sample_keys = list(coolrom_cache.keys())[:20]
print(f"\nAmostra de chaves do cache:")
for k in sample_keys:
    v = coolrom_cache[k]
    print(f"  {k!r}: {str(v)[:80]}")

# Verificar se as chaves são seriais (SLPS-XXXXX) ou nomes
serial_pattern = re.compile(r'^[A-Z]{4}-\d{4,5}$')
serial_keys = [k for k in coolrom_cache.keys() if serial_pattern.match(k)]
name_keys = [k for k in coolrom_cache.keys() if not serial_pattern.match(k)]
print(f"\nChaves por tipo:")
print(f"  Seriais (SLPS-XXXXX): {len(serial_keys)}")
print(f"  Nomes: {len(name_keys)}")

# Carregar pending JP
q = json.load(open(os.path.join(STATE, "queue.json"), "r", encoding="utf-8"))
queue = q.get("queue", [])
jp_pending = {}
for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else str(item)
    name = item.get("name", "") if isinstance(item, dict) else ""
    if serial.startswith(("SLPM", "SLPS", "SLPH", "SCPS", "SIPS")):
        jp_pending[serial] = name

print(f"\nJP pending: {len(jp_pending)}")

# Verificar quantos pending JP estão no cache por serial
in_cache_by_serial = sum(1 for s in jp_pending if s in coolrom_cache)
print(f"JP pending no cache por serial: {in_cache_by_serial}/{len(jp_pending)}")

# Verificar por nome
in_cache_by_name = 0
for serial, name in jp_pending.items():
    if name and name.lower() in [k.lower() for k in name_keys[:100]]:
        in_cache_by_name += 1

# Fazer match por nome mais eficiente
name_lower_cache = {k.lower(): k for k in name_keys}
matches_by_name = []
for serial, name in jp_pending.items():
    if not name:
        continue
    name_lower = name.lower()
    if name_lower in name_lower_cache:
        matches_by_name.append((serial, name, name_lower_cache[name_lower]))
    else:
        # Match parcial
        for cache_name_lower, cache_key in name_lower_cache.items():
            if name_lower in cache_name_lower or cache_name_lower in name_lower:
                matches_by_name.append((serial, name, cache_key))
                break

print(f"JP pending no cache por nome: {len(matches_by_name)}/{len(jp_pending)}")
for s, n, cn in matches_by_name[:10]:
    print(f"  {s}: {n[:30]} -> cache key: {cn[:30]}")

# Verificar seriais JP no cache
jp_serials_in_cache = [k for k in serial_keys if k.startswith(("SLPM", "SLPS", "SLPH", "SCPS", "SIPS"))]
print(f"\nSeriais JP no cache: {len(jp_serials_in_cache)}")
for s in jp_serials_in_cache[:10]:
    print(f"  {s}: {str(coolrom_cache[s])[:80]}")

# Verificar seriais EU/US no cache
eu_serials = [k for k in serial_keys if k.startswith(("SLES", "SCED"))]
us_serials = [k for k in serial_keys if k.startswith(("SLUS", "SCUS"))]
print(f"\nSeriais EU no cache: {len(eu_serials)}")
print(f"Seriais US no cache: {len(us_serials)}")
