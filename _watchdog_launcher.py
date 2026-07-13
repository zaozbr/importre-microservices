"""Launcher para o watchdog — usa subprocess.Popen detached."""
import subprocess, sys, os

PYTHON = sys.executable
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_watchdog_autonomous.py')

# DETACHED_PROCESS = 0x00000008 — separa do console pai mas nao cria novo process group
subprocess.Popen(
    [PYTHON, SCRIPT],
    creationflags=0x00000008,  # DETACHED_PROCESS
)
print(f'Watchdog launched: {PYTHON} {SCRIPT}')
