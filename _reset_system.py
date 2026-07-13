import json
import subprocess
import sys
import time


def get_no_window_kwargs():
    """Retorna kwargs para subprocess.run sem janela e sem roubar foco no Windows."""
    kwargs = {"capture_output": True, "text": True}
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def list_python_processes():
    """Lista todos os processos python.exe com CommandLine (sem PowerShell)."""
    try:
        import psutil
        out = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info.get("name", "").lower() != "python.exe":
                    continue
                out.append({
                    "ProcessId": proc.info["pid"],
                    "CommandLine": " ".join(proc.info.get("cmdline") or [])
                })
            except Exception:
                pass
        return out
    except Exception as e:
        print(f"Erro listando processos: {e}")
        return []


def kill_pid(pid):
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], timeout=10, **get_no_window_kwargs())
        print(f"PID {pid} morto")
    except Exception as e:
        print(f"Erro ao matar PID {pid}: {e}")


def main():
    # Lista de padroes que identificam processos do nosso sistema
    patterns = [
        "importre.py",
        "importre_supervisor.py",
        "importre_server.py",
        "_monitor_importre.py",
        "_chd_convert_v2.py",
        "_chd_supervisor.py",
    ]
    procs = list_python_processes()
    killed = 0
    for p in procs:
        cmdline = p.get("CommandLine", "") or ""
        pid = int(p.get("ProcessId", 0))
        if not pid:
            continue
        if any(pattern in cmdline for pattern in patterns):
            print(f"Matando PID {pid}: {cmdline[:100]}")
            kill_pid(pid)
            killed += 1
    print(f"Total morto: {killed}")
    print("Aguardando 3s...")
    time.sleep(3)


if __name__ == "__main__":
    main()
