# Reinicia o conversor CHD. Nao afeta o importre.
import subprocess
import time
from pathlib import Path

GEN_PARENT = lambda: Path(__file__).parent.resolve()
STOP_CHD = GEN_PARENT() / "_stop_chd.py"
START_CHD = GEN_PARENT() / "_start_chd.py"

print("Reiniciando conversor CHD")
subprocess.run(["python", str(STOP_CHD)], timeout=60)
time.sleep(3)
subprocess.run(["python", str(START_CHD)], timeout=60)
print("Conversor CHD reiniciado. Dashboard: http://127.0.0.1:8766/")
