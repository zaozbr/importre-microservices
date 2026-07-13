"""Loop controller para o watchdog — chama _watchdog_autonomous.py a cada 60s.
Lancado por _watchdog_start.vbs com janela oculta (0).
Usa subprocess.call com CREATE_NO_WINDOW para ping (funciona sem console)."""
import subprocess, sys, os

PYTHON = r"C:\Users\Usuario\AppData\Local\Programs\Python\Python314\python.exe"
SCRIPT = r"D:\roms\library\roms\psx\_watchdog_autonomous.py"
LOG = r"D:\roms\library\roms\_importre_state\watchdog_autonomous.log"
CREATE_NO_WINDOW = 0x08000000

# Limpar log antigo
try:
    os.remove(LOG)
except:
    pass

while True:
    try:
        # Rodar watchdog (1 ciclo, sai com os._exit(0))
        subprocess.call(
            [PYTHON, SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
    except:
        pass
    # Sleep 60s usando ping com CREATE_NO_WINDOW
    try:
        subprocess.call(
            ['ping', '-n', '61', '127.0.0.1'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
    except:
        pass
