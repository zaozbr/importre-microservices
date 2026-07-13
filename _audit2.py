#!/usr/bin/env python3
"""Auditoria complementar - status dos servicos e fila."""
import urllib.request, json, subprocess
from pathlib import Path

# 1. Dashboards
try:
    html = urllib.request.urlopen("http://127.0.0.1:8766/", timeout=10).read().decode("utf-8", errors="replace")
    import re
    nums = re.findall(r">(\d+)<", html[:2000])
    print(f"CHD dashboard: total={nums[0]} ok={nums[1]} falhas={nums[2]} pulados={nums[3]} em_progresso={nums[4]}")
except Exception as e:
    print(f"CHD dashboard OFFLINE: {e}")

try:
    html = urllib.request.urlopen("http://127.0.0.1:8765/", timeout=10).read().decode("utf-8", errors="replace")
    print(f"Importre dashboard: ONLINE ({len(html)} bytes)")
except Exception as e:
    print(f"Importre dashboard OFFLINE: {e}")

# 2. Fila importre
queue_file = Path(r"D:\roms\library\roms\_importre_state\queue.json")
if queue_file.exists():
    try:
        queue = json.loads(queue_file.read_text(encoding="utf-8"))
        if isinstance(queue, list):
            pending = sum(1 for item in queue if item.get("status") == "pending")
            completed = sum(1 for item in queue if item.get("status") == "completed")
            failed = sum(1 for item in queue if item.get("status") == "failed")
            in_progress = sum(1 for item in queue if item.get("status") == "in_progress")
            print(f"Fila importre: total={len(queue)} pending={pending} completed={completed} failed={failed} in_progress={in_progress}")
        elif isinstance(queue, dict):
            items = queue.get("items", queue.get("queue", []))
            if isinstance(items, list):
                pending = sum(1 for item in items if item.get("status") == "pending")
                completed = sum(1 for item in items if item.get("status") == "completed")
                failed = sum(1 for item in items if item.get("status") == "failed")
                in_progress = sum(1 for item in items if item.get("status") == "in_progress")
                print(f"Fila importre: total={len(items)} pending={pending} completed={completed} failed={failed} in_progress={in_progress}")
            else:
                print(f"Fila importre (dict keys): {list(queue.keys())[:10]}")
    except Exception as e:
        print(f"Erro lendo fila: {e}")
        raw = queue_file.read_text(encoding="utf-8", errors="replace")[:300]
        print(f"Primeiros chars: {repr(raw[:200])}")
else:
    print("Arquivo de fila nao encontrado")

# 3. Monitor log
mon_log = Path(r"D:\roms\library\roms\psx\_monitor_8h.log")
if mon_log.exists():
    lines = mon_log.read_text(encoding="utf-8").strip().splitlines()
    print(f"\nMonitor (ultimas 5 linhas):")
    for l in lines[-5:]:
        print(f"  {l}")

# 4. CHD convert log (ultimas linhas)
chd_log = Path(r"D:\roms\library\roms\psx\_chd_convert.log")
if chd_log.exists():
    lines = chd_log.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    print(f"\nCHD convert log (ultimas 5 linhas):")
    for l in lines[-5:]:
        print(f"  {l[:150]}")

# 5. Espaco em disco
for drive in ["D:", "F:"]:
    try:
        result = subprocess.run(
            ["wmic", "logicaldisk", "where", f"DeviceID='{drive}'", "get", "FreeSpace,Size"],
            capture_output=True, text=True, timeout=10
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip() and "FreeSpace" not in l]
        if lines:
            parts = lines[0].split()
            if len(parts) >= 2:
                free = int(parts[0]) / 1024**3
                total = int(parts[1]) / 1024**3
                used = total - free
                print(f"\nDisco {drive}: Total={total:.0f}GB Usado={used:.0f}GB Livre={free:.0f}GB")
    except Exception as e:
        print(f"\nDisco {drive}: erro {e}")

# 6. Processos
print("\nProcessos Python ativos:")
try:
    result = subprocess.run(
        ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
        capture_output=True, text=True, timeout=15
    )
    counts = {}
    for line in result.stdout.splitlines():
        for key in ["_chd_convert", "_chd_supervisor", "_monitor_8h", "importre.py", "importre_supervisor"]:
            if key in line:
                counts[key] = counts.get(key, 0) + 1
    for k, v in counts.items():
        print(f"  {k}: {v}")
except Exception as e:
    print(f"  Erro: {e}")
