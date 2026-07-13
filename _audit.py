#!/usr/bin/env python3
"""Auditoria completa da colecao PSX."""
from pathlib import Path
import os, time, subprocess, json

PSX = Path(r"D:\roms\library\roms\psx")
t0 = time.time()

# === 1. CHDs ===
chds_main = list(PSX.glob("*.chd"))
chds_main_size = sum(f.stat().st_size for f in chds_main)

dup = PSX / "duplicados"
chds_dup = list(dup.glob("*.chd")) if dup.exists() else []
chds_dup_size = sum(f.stat().st_size for f in chds_dup)

inv = PSX / "_chd_invalid_backup"
chds_inv = list(inv.glob("*.chd")) if inv.exists() else []

fail_dir = PSX / "_chd_failed"
chds_fail = list(fail_dir.glob("*.chd")) if fail_dir.exists() else []

# === 2. ROMs nao convertidas ===
rom_exts = {".bin", ".img", ".iso", ".mdf"}
bins_main = [f for f in PSX.glob("*") if f.suffix.lower() in rom_exts]
bins_dup = [f for f in dup.glob("*") if f.suffix.lower() in rom_exts] if dup.exists() else []
cues_main = list(PSX.glob("*.cue"))
cues_dup = list(dup.glob("*.cue")) if dup.exists() else []
ecms = list(PSX.rglob("*.ecm"))

# === 3. Downloads em andamento ===
parts = list(PSX.rglob("*.part")) + list(PSX.rglob("*.tmp")) + list(PSX.rglob("*.crdownload"))

# === 4. BINs sem CHD na pasta principal ===
chd_stems = set()
for c in chds_main:
    chd_stems.add(c.stem.lower())
bins_without_chd = []
for b in bins_main:
    # Normalizar: remover serial para comparar
    stem = b.stem.lower()
    # Tentar match direto ou fuzzy
    found = False
    for cs in chd_stems:
        if stem in cs or cs in stem:
            found = True
            break
    if not found:
        bins_without_chd.append(b)

# === 5. Status do conversor CHD ===
chd_status = "unknown"
try:
    import urllib.request, re
    html = urllib.request.urlopen("http://127.0.0.1:8766/", timeout=10).read().decode("utf-8", errors="replace")
    nums = re.findall(r">(\d+)<", html[:2000])
    if len(nums) >= 5:
        chd_status = f"total={nums[0]} ok={nums[1]} falhas={nums[2]} pulados={nums[3]} em_progresso={nums[4]}"
except Exception:
    chd_status = "OFFLINE"

# === 6. Status do importre ===
imp_status = "unknown"
try:
    html = urllib.request.urlopen("http://127.0.0.1:8765/", timeout=10).read().decode("utf-8", errors="replace")
    if "importre" in html.lower():
        imp_status = "ONLINE"
    else:
        imp_status = "respondendo"
except Exception:
    imp_status = "OFFLINE"

# === 7. Estado da fila importre ===
fila = {}
state_dir = Path(r"D:\roms\library\roms\_importre_state")
queue_file = state_dir / "queue.json"
if queue_file.exists():
    try:
        queue = json.loads(queue_file.read_text(encoding="utf-8"))
        pending = sum(1 for item in queue if item.get("status") == "pending")
        completed = sum(1 for item in queue if item.get("status") == "completed")
        failed = sum(1 for item in queue if item.get("status") == "failed")
        in_progress = sum(1 for item in queue if item.get("status") == "in_progress")
        fila = {"pending": pending, "completed": completed, "failed": failed, "in_progress": in_progress, "total": len(queue)}
    except Exception:
        fila = {"error": "parse"}

# === 8. Espaco em disco ===
disk = {}
try:
    usage = psutil.disk_usage(str(PSX))
    disk = {"total_gb": usage.total/1024**3, "used_gb": usage.used/1024**3, "free_gb": usage.free/1024**3}
except Exception:
    try:
        result = subprocess.run(["fsutil", "volume", "diskfree", "D:"], capture_output=True, text=True, timeout=10)
        disk = {"raw": result.stdout[:200]}
    except Exception:
        disk = {"error": "unavailable"}

# === 9. CHDs por tamanho (distribuicao) ===
sizes = []
for c in chds_main:
    sizes.append(c.stat().st_size / (1024*1024))
sizes.sort()
size_buckets = {"<1MB": 0, "1-10MB": 0, "10-100MB": 0, "100-500MB": 0, "500MB-1GB": 0, ">1GB": 0}
for s in sizes:
    if s < 1: size_buckets["<1MB"] += 1
    elif s < 10: size_buckets["1-10MB"] += 1
    elif s < 100: size_buckets["10-100MB"] += 1
    elif s < 500: size_buckets["100-500MB"] += 1
    elif s < 1000: size_buckets["500MB-1GB"] += 1
    else: size_buckets[">1GB"] += 1

# === 10. Processos rodando ===
procs = {}
try:
    result = subprocess.run(
        ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
        capture_output=True, text=True, timeout=15
    )
    for line in result.stdout.splitlines():
        if "_chd_convert" in line: procs["chd_convert"] = procs.get("chd_convert", 0) + 1
        if "_chd_supervisor" in line: procs["chd_supervisor"] = procs.get("chd_supervisor", 0) + 1
        if "_monitor_8h" in line: procs["monitor_8h"] = procs.get("monitor_8h", 0) + 1
        if "importre.py" in line and "supervisor" not in line: procs["importre"] = procs.get("importre", 0) + 1
        if "importre_supervisor" in line: procs["importre_supervisor"] = procs.get("importre_supervisor", 0) + 1
except Exception:
    pass

# === RELATORIO ===
print("=" * 60)
print("  AUDITORIA DA COLECAO PSX")
print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)
print()
print("--- CHDs CONVERTIDOS ---")
print(f"  CHDs pasta principal:  {len(chds_main):>5}  ({chds_main_size/1024**3:.1f} GB)")
print(f"  CHDs duplicados:       {len(chds_dup):>5}  ({chds_dup_size/1024**3:.1f} GB)")
print(f"  CHDs invalidos backup: {len(chds_inv):>5}")
print(f"  CHDs em _chd_failed:   {len(chds_fail):>5}")
total_valid = len(chds_main) + len(chds_dup)
total_size = chds_main_size + chds_dup_size
print(f"  TOTAL CHDs validos:    {total_valid:>5}  ({total_size/1024**3:.1f} GB)")
print()
print("--- DISTRIBUICAO POR TAMANHO ---")
for bucket, count in size_buckets.items():
    bar = "#" * (count // 50)
    print(f"  {bucket:>12}: {count:>5}  {bar}")
print()
print("--- ROMs NAO CONVERTIDAS ---")
print(f"  BINs/IMGs/ISOs (main): {len(bins_main):>5}")
print(f"  BINs/IMGs/ISOs (dup):  {len(bins_dup):>5}")
print(f"  CUEs (main):           {len(cues_main):>5}")
print(f"  CUEs (dup):            {len(cues_dup):>5}")
print(f"  ECMs:                  {len(ecms):>5}")
print(f"  BINs sem CHD (main):   {len(bins_without_chd):>5}")
print()
print("--- DOWNLOADS EM ANDAMENTO ---")
print(f"  Arquivos .part/.tmp:   {len(parts):>5}")
print()
print("--- STATUS DOS SERVICOS ---")
print(f"  Conversor CHD:  {chd_status}")
print(f"  Importre:       {imp_status}")
print(f"  Processos Python:")
for name, count in procs.items():
    print(f"    {name:>20}: {count}")
print()
print("--- FILA DO IMPORTRE ---")
if "error" in fila:
    print(f"  Erro ao ler fila: {fila['error']}")
elif fila:
    print(f"  Total:     {fila.get('total', '?')}")
    print(f"  Pendentes: {fila.get('pending', '?')}")
    print(f"  Completos: {fila.get('completed', '?')}")
    print(f"  Falhos:    {fila.get('failed', '?')}")
    print(f"  Em prog:   {fila.get('in_progress', '?')}")
else:
    print("  Fila nao encontrada")
print()
print("--- ESPACO EM DISCO ---")
if "total_gb" in disk:
    print(f"  Total:  {disk['total_gb']:.0f} GB")
    print(f"  Usado:  {disk['used_gb']:.0f} GB")
    print(f"  Livre:  {disk['free_gb']:.0f} GB")
elif "raw" in disk:
    print(f"  {disk['raw'][:150]}")
else:
    print(f"  {disk.get('error', 'indisponivel')}")
print()
print(f"  Tempo de auditoria: {time.time()-t0:.1f}s")
print("=" * 60)
