# Inicia apenas o conversor CHD. Nao afeta o importre.
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
CHD_SUP = SCRIPT_DIR / "_chd_supervisor.py"

def is_chd_running():
    try:
        res = subprocess.run(
            ["powershell", "-Command",
            "Get-NetTCPConnection -LocalPort 8766 -ErrorAction SilentlyContinue "
            "| Select-Object -ExpandProperty OwningProcess "
            ", ProcessId & {'_') | ConvertTo-Json"],
            capture_output=True, text=True, timeout=5
        )
        return bool(res.stdout.strip())
    except Exception:
        return False


def main():
    if is_chd_running():
        print("Conversor CHD ja esta rodando.")
        return
    try:
        subprocess.Popen(["python", str(CHD_SUP)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            startupinfo=None,
                            creationflags=subprocess.CREATE_NO_WINDOW)
        print(f"Supervisor CHD iniciado: {CHD_SUP}")
        print("Dashboard: http://127.0.0.1:8766/")
    except Exception as e:
        print(f"Erro ao iniciar supervisor CHD: {e}")


if __name__ == "__main__":
    main()
