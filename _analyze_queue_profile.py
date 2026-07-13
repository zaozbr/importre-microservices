"""Analisa perfil da fila: JP vs EU/US, cobertura por fonte."""
import json
import os

q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
queue = q.get("queue", [])

# Categorizar por região
jp = []  # SLPM, SLPS, SLPH, SCPS, SIPS
eu = []  # SLES, SCED
us = []  # SLUS, SCUS
other = []

for item in queue:
    serial = item.get("serial", "") if isinstance(item, dict) else str(item)
    if serial.startswith(("SLPM", "SLPS", "SLPH", "SCPS", "SIPS", "SLPD")):
        jp.append(serial)
    elif serial.startswith(("SLES", "SCED")):
        eu.append(serial)
    elif serial.startswith(("SLUS", "SCUS")):
        us.append(serial)
    else:
        other.append(serial)

print(f"=== PERFIL DA FILA ({len(queue)} pending) ===")
print(f"  JP (SLPM/SLPS/SCPS):  {len(jp)} ({100*len(jp)/len(queue):.0f}%)")
print(f"  EU (SLES/SCED):       {len(eu)} ({100*len(eu)/len(queue):.0f}%)")
print(f"  US (SLUS/SCUS):       {len(us)} ({100*len(us)/len(queue):.0f}%)")
print(f"  Other:                {len(other)} ({100*len(other)/len(queue):.0f}%)")

# Verificar cobertura do coolrom_cache
coolrom_cache = json.load(open(r"D:\roms\library\roms\_importre_state\coolrom_cache.json", "r", encoding="utf-8"))
print(f"\n=== COBERTURA COOLROM ===")
jp_in_coolrom = sum(1 for s in jp if s in coolrom_cache)
eu_in_coolrom = sum(1 for s in eu if s in coolrom_cache)
us_in_coolrom = sum(1 for s in us if s in coolrom_cache)
print(f"  JP no cache: {jp_in_coolrom}/{len(jp)} ({100*jp_in_coolrom/max(len(jp),1):.0f}%)")
print(f"  EU no cache: {eu_in_coolrom}/{len(eu)} ({100*eu_in_coolrom/max(len(eu),1):.0f}%)")
print(f"  US no cache: {us_in_coolrom}/{len(us)} ({100*us_in_coolrom/max(len(us),1):.0f}%)")

# Verificar cobertura do archive_jp_public_index
archive_jp_index = {}
for idx_name in ["archive_jp_public_index.json", "archive_jp_index.json", "archive_name_index.json"]:
    p = os.path.join(r"D:\roms\library\roms\_importre_state", idx_name)
    if os.path.exists(p):
        idx = json.load(open(p, "r", encoding="utf-8"))
        archive_jp_index.update(idx)
print(f"\n=== COBERTURA ARCHIVE.ORG JP ===")
jp_in_archive = sum(1 for s in jp if s in archive_jp_index)
print(f"  JP no índice archive: {jp_in_archive}/{len(jp)} ({100*jp_in_archive/max(len(jp),1):.0f}%)")

# Verificar failed
failed = q.get("failed", {})
if isinstance(failed, dict):
    failed_jp = sum(1 for s in failed.keys() if s.startswith(("SLPM", "SLPS", "SLPH", "SCPS", "SIPS")))
    failed_eu = sum(1 for s in failed.keys() if s.startswith(("SLES", "SCED")))
    failed_us = sum(1 for s in failed.keys() if s.startswith(("SLUS", "SCUS")))
    print(f"\n=== FALHAS POR REGIÃO ({len(failed)} total) ===")
    print(f"  JP: {failed_jp}, EU: {failed_eu}, US: {failed_us}")

# Mostrar amostra de JP pending
print(f"\n=== AMOSTRA JP PENDING (primeiros 20) ===")
for s in jp[:20]:
    in_coolrom = "✓" if s in coolrom_cache else "✗"
    in_archive = "✓" if s in archive_jp_index else "✗"
    print(f"  {s}: coolrom={in_coolrom} archive={in_archive}")
