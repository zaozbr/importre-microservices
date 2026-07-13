"""Roda importre.main() com captura de erros."""
import sys, traceback
sys.path.insert(0, r"D:\roms\library\roms\psx")

# Patch sys.argv para simular linha de comando
sys.argv = [
    "importre.py",
    "--workers", "10",
    "--rounds", "999",
    "--limit", "999",
    "--no-server",
]

try:
    print("Iniciando importre.main()...", flush=True)
    import importre
    importre.main()
    print("main() retornou normalmente", flush=True)
except SystemExit as e:
    print(f"SYSTEM EXIT: code={e.code}", flush=True)
    traceback.print_exc()
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    traceback.print_exc()
