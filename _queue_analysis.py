"""Analisa a fila: quantos itens tem serial real vs NOSERIAL."""
import json
from pathlib import Path
from collections import Counter

qpath = Path(r"D:\roms\library\roms\_importre_state\queue.json")
with open(qpath, "r", encoding="utf-8") as f:
    q = json.load(f)

queue = q.get("queue", [])
in_prog = q.get("in_progress", {})
completed = q.get("completed", {})

# Categorizar
real_serials = 0
noserials = 0
homebrews = 0
regions = Counter()

for item in queue:
    serial = item.get("serial", "")
    if serial.startswith("NOSERIAL"):
        noserials += 1
    elif serial.startswith("HBREW") or serial.startswith("HOMEBREW") or serial.startswith("BREW"):
        homebrews += 1
    else:
        real_serials += 1
    # Regiao
    if serial.startswith("SLUS") or serial.startswith("SCUS"):
        regions["USA"] += 1
    elif serial.startswith("SLES") or serial.startswith("SCES"):
        regions["EU"] += 1
    elif serial.startswith("SLPM") or serial.startswith("SLPS") or serial.startswith("SCPS"):
        regions["JP"] += 1
    elif serial.startswith("NOSERIAL"):
        regions["NOSERIAL"] += 1
    else:
        regions["OTHER"] += 1

print(f"=== FILA ({len(queue)} itens) ===")
print(f"Serials reais: {real_serials}")
print(f"NOSERIAL: {noserials}")
print(f"Homebrew: {homebrews}")
print(f"Regioes: {dict(regions)}")

# In progress
ip_real = 0
ip_noser = 0
for serial in in_prog:
    if serial.startswith("NOSERIAL"):
        ip_noser += 1
    else:
        ip_real += 1
print(f"\n=== EM PROGRESSO ({len(in_prog)}) ===")
print(f"Serials reais: {ip_real}")
print(f"NOSERIAL: {ip_noser}")

# Completed
print(f"\n=== COMPLETADOS: {len(completed)} ===")

# Mostrar primeiros 10 itens com serial real
print("\n=== Primeiros 10 itens com serial real na fila ===")
count = 0
for item in queue:
    serial = item.get("serial", "")
    if not serial.startswith("NOSERIAL"):
        print(f"  {serial}: {item.get('name', '')[:50]}")
        count += 1
        if count >= 10:
            break
