"""Launcher robusto para importre.py — usa python.exe com log para arquivo."""
import subprocess, sys, os

PYTHON = r"C:\Users\Usuario\AppData\Local\Programs\Python\Python314\python.exe"
IMPORTRE = r"D:\roms\library\roms\psx\importre.py"
CWD = r"D:\roms\library\roms"
STDOUT_LOG = r"D:\roms\library\roms\psx\_importre_stdout.log"

try:
    os.remove(STDOUT_LOG)
except:
    pass

p = subprocess.Popen(
    [PYTHON, IMPORTRE, '--workers', '8', '--rounds', '999', '--limit', '999', '--no-server'],
    cwd=CWD,
    stdout=open(STDOUT_LOG, 'w'),
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
)
print(f'importre.py iniciado PID={p.pid}')
print(f'log: {STDOUT_LOG}')
