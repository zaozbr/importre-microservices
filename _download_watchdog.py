#!/usr/bin/env python3
"""
_download_watchdog.py — Monitor autonomo de downloads.

Garante que o importre.py esteja sempre baixando dados. Se detectar:
- Downloads ativos mas sem progresso (>60s em 0 bytes)
- Nenhum download ativo por >5 min com fila cheia
- Processo importre.py morto

Toma ação: loga, reinicia importre.py via supervisor, e envia alertas.

Roda em loop infinito."""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def get_no_window_kwargs():
    """Retorna kwargs para subprocess.Popen/run sem janela e sem roubar foco no Windows."""
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
        )
    return kwargs

STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
LOG_PATH = STATE_DIR / "download_watchdog.log"
DL_PROGRESS_PATH = STATE_DIR / "dl_progress.json"
QUEUE_PATH = STATE_DIR / "queue.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("download_watchdog")


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else default
    except Exception:
        return default


def get_importre_pids():
    """Retorna PIDs do importre.py principal (sem PowerShell, evita janelas piscando)."""
    pids = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = proc.info.get("cmdline") or []
                cmdline = " ".join(cmd)
                if proc.info.get("name", "").lower() == "python.exe" and "importre.py" in cmdline:
                    if "supervisor" not in cmdline and "importre_server" not in cmdline:
                        pids.append(proc.info["pid"])
            except Exception:
                pass
    except Exception as e:
        log.debug(f"Erro listando PIDs via psutil: {e}")
    return pids


def restart_importre():
    """Reinicia importre.py via supervisor. Mata processos atuais e deixa o monitor sobe-los."""
    log.warning("REINICIANDO importre.py por falta de progresso de download")
    pids = get_importre_pids()
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, **get_no_window_kwargs())
            log.info(f"Mato PID {pid}")
        except Exception as e:
            log.warning(f"Erro matando {pid}: {e}")


def check_downloads():
    """Verifica se ha downloads ativos com progresso real."""
    dl = load_json(DL_PROGRESS_PATH, {})
    now = time.time()
    active = 0
    stuck = 0
    moving = 0
    total_speed = 0
    for serial, info in dl.items():
        ts = info.get("ts", 0)
        age = now - ts
        if age > 30:
            continue
        active += 1
        downloaded = info.get("downloaded", 0)
        speed = info.get("speed", 0)
        total_speed += speed
        if downloaded == 0 and age > 20:
            stuck += 1
        else:
            moving += 1
    return active, moving, stuck, total_speed


def check_queue():
    data = load_json(QUEUE_PATH, {})
    pending = len(data.get("queue", []))
    in_progress = len(data.get("in_progress", {}))
    completed = len(data.get("completed", {}))
    failed = len(data.get("failed", {}))
    return pending, in_progress, completed, failed


def main():
    log.info("Download watchdog iniciado")
    last_moving_time = time.time()
    last_action_time = 0
    no_download_counter = 0

    while True:
        try:
            active, moving, stuck, total_speed = check_downloads()
            pending, in_progress, completed, failed = check_queue()

            log.info(
                f"Active={active} Moving={moving} Stuck={stuck} Speed={total_speed/1024/1024:.1f}MB/s "
                f"Pending={pending} InProgress={in_progress} Completed={completed} Failed={failed}"
            )

            if moving > 0:
                last_moving_time = time.time()
                no_download_counter = 0

            # Se ha downloads ativos mas todos presos em 0 bytes por muito tempo
            if active > 0 and moving == 0:
                no_download_counter += 1
                log.warning(f"Downloads travados em 0 bytes ({no_download_counter}/3)")
                if no_download_counter >= 3:
                    if time.time() - last_action_time > 300:
                        restart_importre()
                        last_action_time = time.time()
                        no_download_counter = 0

            # Se nao ha downloads ativos e a fila esta cheia
            elif active == 0 and pending > 100 and time.time() - last_moving_time > 300:
                log.warning("Sem downloads ativos por 5min com fila cheia")
                if time.time() - last_action_time > 300:
                    restart_importre()
                    last_action_time = time.time()

            # Se importre.py nao esta rodando
            if not get_importre_pids():
                log.warning("importre.py nao encontrado")
                if time.time() - last_action_time > 60:
                    restart_importre()
                    last_action_time = time.time()

        except Exception as e:
            log.error(f"Erro no watchdog: {e}")

        time.sleep(60)


if __name__ == "__main__":
    main()
