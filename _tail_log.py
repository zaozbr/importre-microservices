"""Lê últimas 30 linhas do importre.log."""
import os
log = r"D:\roms\library\roms\_importre_state\importre.log"
if os.path.exists(log):
    lines = open(log, "r", encoding="utf-8", errors="replace").readlines()
    for l in lines[-30:]:
        print(l.rstrip())
else:
    print("log não encontrado")
