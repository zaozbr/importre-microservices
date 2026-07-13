#!/usr/bin/env python3
"""Monitor autonomo do conversor CHD por 8 horas."""
import urllib.request
import subprocess
import sys
import time
import re
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DASHBOARD = "http://127.0.0.1:8766/"
LOG_FILE = PSX / "_monitor_8h.log"
END_TIME = time.time() + 8 * 3600
CHECK_INTERVAL = 120


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_dashboard():
    try:
        resp = urllib.request.urlopen(DASHBOARD, timeout=15)
        return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def parse_dashboard(html):
    if not html:
        return None
    nums = re.findall(r">(\d+)<", html[:2000])
    if len(nums) < 5:
        return None
    return {
        "total": int(nums[0]),
        "ok": int(nums[1]),
        "falhas": int(nums[2]),
        "pulados": int(nums[3]),
        "em_progresso": int(nums[4]),
    }


def is_port_listening():
    try:
        urllib.request.urlopen(DASHBOARD, timeout=10)
        return True
    except Exception:
        return False


def restart_chd():
    log("Reiniciando conversor CHD...")
    try:
        subprocess.run(
            [sys.executable, str(PSX / "_stop_chd.py")],
            capture_output=True, text=True, timeout=60
        )
        time.sleep(3)
        subprocess.run(
            [sys.executable, str(PSX / "_start_chd.py")],
            capture_output=True, text=True, timeout=60
        )
        time.sleep(10)
        if is_port_listening():
            log("Conversor CHD reiniciado com sucesso")
            return True
        log("ERRO: Conversor CHD nao subiu apos restart")
        return False
    except Exception as e:
        log(f"ERRO ao reiniciar: {e}")
        return False


def check_supervisor():
    """Verifica se o supervisor CHD esta rodando via wmic."""
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'",
             "get", "ProcessId,CommandLine"],
            capture_output=True, text=True, timeout=10
        )
        return "_chd_supervisor" in result.stdout
    except Exception:
        return False


def start_supervisor():
    if check_supervisor():
        return  # ja rodando, nao duplicar
    try:
        subprocess.Popen(
            [sys.executable, str(PSX / "_chd_supervisor.py")],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log("Supervisor CHD iniciado")
    except Exception as e:
        log(f"ERRO ao iniciar supervisor: {e}")


def clean_temp_files():
    temp_dir = Path(r"F:\chd_temp")
    if not temp_dir.exists():
        return
    now = time.time()
    removed = 0
    for f in temp_dir.glob("_cue_*.cue"):
        try:
            if now - f.stat().st_mtime > 3600:
                f.unlink()
                removed += 1
        except Exception:
            pass
    if removed:
        log(f"Limpos {removed} CUEs temporarios orfaos")


log("=== Monitor 8h iniciado ===")
log(f"Termina em {time.strftime('%H:%M:%S', time.localtime(END_TIME))}")

last_done = 0  # ok + falhas + pulados
last_total = 0
stall_count = 0
clean_counter = 0
restart_count = 0
MAX_RESTARTS = 20

while time.time() < END_TIME:
    try:
        html = get_dashboard()
        stats = parse_dashboard(html)

        if stats is None:
            log("Dashboard nao responde. Tentando reiniciar...")
            if restart_count < MAX_RESTARTS:
                restart_chd()
                restart_count += 1
            else:
                log("Limite de restarts atingido. Parando monitor.")
                break
            time.sleep(CHECK_INTERVAL)
            continue

        done = stats["ok"] + stats["falhas"] + stats["pulados"]

        # Detectar estagnacao: sem progresso em done E sem em_progresso
        if done == last_done and stats["em_progresso"] == 0 and stats["total"] > 0:
            stall_count += 1
            log(f"Possivel estagnacao (done={done}, total={stats['total']})")
            if stall_count >= 3:
                log("Estagnacao confirmada. Reiniciando...")
                if restart_count < MAX_RESTARTS:
                    restart_chd()
                    restart_count += 1
                stall_count = 0
        else:
            stall_count = 0

        if done != last_done or stats["total"] != last_total:
            pct = 100.0 * done / max(stats["total"], 1)
            log(f"Progresso: {done}/{stats['total']} ({pct:.1f}%) | OK={stats['ok']} Falhas={stats['falhas']} Pulados={stats['pulados']} EmProgresso={stats['em_progresso']}")
            last_done = done
            last_total = stats["total"]

        clean_counter += 1
        if clean_counter >= 15:
            clean_temp_files()
            clean_counter = 0

        if (stats["total"] > 0
            and done >= stats["total"]
            and stats["em_progresso"] == 0):
            log(f"Conversao completa! OK={stats['ok']}, Falhas={stats['falhas']}, Pulados={stats['pulados']}")
            log("Aguardando novas ROMs do importre... (monitor continua ativo)")
            time.sleep(CHECK_INTERVAL * 5)  # Esperar 10min antes de checar de novo
            # Reiniciar conversor para re-escanear
            restart_chd()
            continue

    except Exception as e:
        log(f"ERRO no loop: {e}")

    time.sleep(CHECK_INTERVAL)

log("=== Monitor 8h finalizado ===")
