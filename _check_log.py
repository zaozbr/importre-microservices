"""Verifica log e estado do importre."""
import os
from pathlib import Path

log_path = Path(r"D:\roms\library\roms\_importre_state\importre.log")
if log_path.exists():
    stat = log_path.stat()
    print(f"Log size: {stat.st_size} bytes")
    print(f"Log mtime: {os.path.getmtime(log_path)}")
    # Ler ultimas 20 linhas
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    print(f"Total lines: {len(lines)}")
    for line in lines[-20:]:
        print(line.rstrip())
else:
    print("Log nao encontrado")

# Verificar out log
out_path = Path(r"D:\roms\library\roms\_importre_state\importre_out.log")
if out_path.exists():
    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    print(f"\n=== OUT LOG ({len(lines)} lines) ===")
    for line in lines[-20:]:
        print(line.rstrip())

# Verificar err log
err_path = Path(r"D:\roms\library\roms\_importre_state\importre_err.log")
if err_path.exists() and err_path.stat().st_size > 0:
    with open(err_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    print(f"\n=== ERR LOG ===\n{content[:2000]}")
