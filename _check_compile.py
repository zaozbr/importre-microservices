"""Verifica se importre.py compila sem erros."""
import py_compile
import sys
for f in [r"D:\roms\library\roms\psx\importre.py", r"D:\roms\library\roms\psx\_watchdog_autonomous.py", r"D:\roms\library\roms\psx\_aria2_manager.py"]:
    try:
        py_compile.compile(f, doraise=True)
        print(f"{f.split(chr(92))[-1]}: OK")
    except py_compile.PyCompileError as e:
        print(f"ERRO em {f}: {e}")
        sys.exit(1)
