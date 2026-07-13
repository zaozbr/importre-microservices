#!/usr/bin/env python3
"""Monitor do conversor CHD PSX. Reporta progresso a cada 5 minutos."""
import sys, time, re, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

LOG_FILE = Path(r"D:\roms\library\roms\psx\_chd_monitor_5min.log")
INTERVAL = 300

def mon_log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def get_dashboard():
    try:
        html = urllib.request.urlopen("http://127.0.0.1:8766/", timeout=10).read().decode("utf-8", errors="replace")
        nums = re.findall(r">(\d+)<", html[:2000])
        if len(nums) >= 5:
            return {
                "total": int(nums[0]),
                "ok": int(nums[1]),
                "falhas": int(nums[2]),
                "pulados": int(nums[3]),
                "em_progresso": int(nums[4]),
            }
    except:
        pass
    return None

def get_run_kwargs(timeout=None):
    kwargs = {"capture_output": True, "text": True}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def is_running():
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
            **get_run_kwargs(15)
        )
        return "_chd_convert" in result.stdout or "_chd_supervisor" in result.stdout
    except:
        return False

def restart_supervisor():
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        subprocess.Popen(
            ["python", r"D:\roms\library\roms\psx\_chd_supervisor.py"],
            creationflags=0x08000000,
            startupinfo=startupinfo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        mon_log("Supervisor reiniciado!")
    except Exception as e:
        mon_log(f"Erro ao reiniciar: {e}")

def main():
    mon_log("=" * 60)
    mon_log("MONITOR CONVERSOR CHD PSX (5min)")
    mon_log("=" * 60)

    while True:
        try:
            dash = get_dashboard()
            running = is_running()

            if dash:
                pct = 100 * (dash["ok"] + dash["falhas"] + dash["pulados"]) / max(dash["total"], 1)
                mon_log(
                    f"Progresso: {dash['ok']+dash['falhas']+dash['pulados']}/{dash['total']} ({pct:.1f}%) | "
                    f"OK={dash['ok']} FAIL={dash['falhas']} SKIP={dash['pulados']} "
                    f"EM_PROG={dash['em_progresso']} | "
                    f"Proc={'OK' if running else 'MORTO'}"
                )
            else:
                mon_log(f"Dashboard offline | Proc={'OK' if running else 'MORTO'}")

            if not running:
                mon_log("Processo morto! Reiniciando supervisor...")
                restart_supervisor()
                time.sleep(15)
                continue

        except Exception as e:
            mon_log(f"ERRO: {e}")

        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
