#!/usr/bin/env python3
"""Relatorio consolidado de 5 minutos."""
import sys, time, urllib.request, re, json, subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

print("=== RELATORIO 5min ===")
print()

# 1. CHD conversor
try:
    html = urllib.request.urlopen("http://127.0.0.1:8766/", timeout=10).read().decode("utf-8", errors="replace")
    nums = re.findall(r">(\d+)<", html[:2000])
    if len(nums) >= 5:
        print(f"CHD conversor: total={nums[0]} ok={nums[1]} falhas={nums[2]} pulados={nums[3]} em_prog={nums[4]}")
except Exception as e:
    print(f"CHD conversor: offline")

# 2. importre
try:
    html = urllib.request.urlopen("http://127.0.0.1:8765/", timeout=10).read().decode("utf-8", errors="replace")
    nums = re.findall(r">(\d+)<", html[:3000])
    if len(nums) >= 4:
        print(f"importre: pendentes={nums[0]} em_andamento={nums[1]} completados={nums[2]} falhados={nums[3]}")
except Exception as e:
    print(f"importre: offline")

# 3. DuckStation
p = Path(r"D:\roms\library\roms\psx\_duck_test.log")
if p.exists():
    lines = p.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if lines:
        print(f"DuckTest: {lines[-1][:120]}")

# 4. Monitor CHD
p2 = Path(r"D:\roms\library\roms\psx\_chd_monitor_5min.log")
if p2.exists():
    lines = p2.read_text(encoding="utf-8").strip().splitlines()
    if lines:
        print(f"Monitor CHD: {lines[-1][:120]}")

# 5. Monitor Duck
p3 = Path(r"D:\roms\library\roms\psx\_duck_monitor.log")
if p3.exists():
    lines = p3.read_text(encoding="utf-8").strip().splitlines()
    if lines:
        print(f"Monitor Duck: {lines[-1][:120]}")

# 6. Processos
result = subprocess.run(
    ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
    capture_output=True, text=True, timeout=15
)
procs = {"chd_convert": 0, "chd_supervisor": 0, "importre.py": 0, "importre_supervisor": 0, "duck_test": 0, "monitor_duck": 0}
for line in result.stdout.splitlines():
    for k in procs:
        if k in line:
            procs[k] = 1
active = sum(procs.values())
print(f"\nProcessos: {active}/6 ativos")
for k, v in procs.items():
    if not v:
        print(f"  MORTO: {k}")
