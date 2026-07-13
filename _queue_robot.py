"""_queue_robot.py — unico escritor da fila central.

Responsabilidades:
  - Atribui itens da fila para workers idle.
  - Le estados dos workers (_importre_state/workers/*.json).
  - Processa eventos (_importre_state/events/*.json).
  - Atualiza queue.json e dl_progress.json.
  - Detecta workers travados e devolve itens para fila.

Regras:
  - Nenhum worker escreve diretamente em queue.json ou dl_progress.json.
  - Robot roda em loop a cada 2s.
  - Eventos sao processados uma unica vez e deletados.
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from _worker_state import (
    STATE_DIR, WORKERS_DIR, EVENTS_DIR,
    get_all_worker_states, get_pending_events, ack_event,
    cleanup_old_worker_files,
)

from importre import file_lock, file_unlock, load_json, save_json

QUEUE_PATH = STATE_DIR / "queue.json"
DL_PROGRESS_PATH = STATE_DIR / "dl_progress.json"
ROBOT_LOG_PATH = STATE_DIR / "queue_robot.log"

STALE_ITEM_SECONDS = 600


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [ROBOT] {msg}"
    try:
        with open(ROBOT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        print(line, flush=True)
    except Exception:
        pass


def load_queue():
    try:
        return load_json(QUEUE_PATH, {"queue": [], "in_progress": {}, "completed": {}, "failed": {}, "retry_count": {}})
    except Exception as e:
        log(f"Erro ao ler queue.json: {e}")
        return {"queue": [], "in_progress": {}, "completed": {}, "failed": {}, "retry_count": {}}


def save_queue(data):
    try:
        save_json(QUEUE_PATH, data)
    except Exception as e:
        log(f"Erro ao salvar queue.json: {e}")


def load_dl_progress():
    if not DL_PROGRESS_PATH.exists():
        return {}
    try:
        with open(DL_PROGRESS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_dl_progress(data):
    tmp = str(DL_PROGRESS_PATH) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(DL_PROGRESS_PATH))
    except Exception as e:
        log(f"Erro ao salvar dl_progress.json: {e}")


def _assign_item_to_worker(worker_id, item, in_progress):
    """Atribui um item a um worker idle e marca em in_progress."""
    serial = item["serial"]
    in_progress[serial] = dict(item)
    in_progress[serial]["_phase"] = "assigned"
    in_progress[serial]["_current_site"] = ""
    in_progress[serial]["_detail"] = "assigned by robot"
    in_progress[serial]["_worker"] = worker_id
    in_progress[serial]["_started_at"] = datetime.now().isoformat()
    # Worker le atribuicao do seu proprio arquivo
    from _worker_state import save_worker_state
    save_worker_state(worker_id, {
        "type": "assigned",
        "serial": serial,
        "name": item.get("name", ""),
        "site": "",
        "phase": "assigned",
        "detail": "assigned by robot",
        "ts": time.time(),
    })
    return serial


def robot_cycle():
    now = time.time()
    states = get_all_worker_states()
    events = get_pending_events()

    fl = file_lock(timeout=5)
    try:
        data = load_queue()
        in_progress = data.get("in_progress", {})
        completed = data.get("completed", {})
        failed = data.get("failed", {})
        retry_count = data.get("retry_count", {})
        queue = data.get("queue", [])

        # 1) Processar eventos (completed/failed/stuck)
        completed_now = 0
        failed_now = 0
        for event in events:
            ev_type = event.get("event")
            serial = event.get("serial", "")
            site = event.get("site", "")
            detail = event.get("detail", "")
            extra = event.get("extra", {})
            if not serial:
                ack_event(event)
                continue
            if ev_type == "completed":
                item = in_progress.pop(serial, {"serial": serial, "name": extra.get("name", detail)})
                completed[serial] = {
                    "site": site,
                    "ts": time.time(),
                    "name": item.get("name", ""),
                    "file": extra.get("file", ""),
                }
                completed_now += 1
                log(f"Completado: {serial} via {site}")
            elif ev_type == "failed":
                item = in_progress.pop(serial, {"serial": serial, "name": extra.get("name", detail)})
                retries = retry_count.get(serial, 0) + 1
                if retries >= 3:
                    failed[serial] = {"site": site, "ts": time.time(), "reason": detail, "name": item.get("name", "")}
                    log(f"Falhou definitivo: {serial} via {site} ({detail})")
                else:
                    retry_count[serial] = retries
                    queue.insert(0, item)
                    log(f"Retry {retries}/3: {serial}")
                failed_now += 1
            elif ev_type == "stuck":
                if serial in in_progress:
                    item = in_progress.pop(serial)
                    queue.insert(0, item)
                    log(f"Stuck drenado: {serial}")
            ack_event(event)

        # 2) Drenar itens presos (sem worker ativo)
        active_serials = set(st.get("serial", "") for st in states.values() if st.get("serial"))
        stale_count = 0
        for serial in list(in_progress.keys()):
            if serial in active_serials:
                continue
            item = in_progress.pop(serial)
            for key in ["_phase", "_current_site", "_detail", "_worker", "_started_at"]:
                item.pop(key, None)
            if serial not in completed and serial not in failed:
                queue.insert(0, item)
                stale_count += 1
                log(f"Orphan drenado: {serial}")

        # 3) Atribuir itens a workers idle
        assigned_count = 0
        idle_workers = [wid for wid, st in states.items() if st.get("type", "idle") == "idle" and not st.get("serial")]
        for worker_id in idle_workers:
            if not queue:
                break
            # Pular se worker ja tem atribuicao recente
            item = queue.pop(0)
            if isinstance(item, str):
                item = {"serial": item, "name": ""}
            serial = item.get("serial")
            if not serial or serial in completed or serial in failed or serial in in_progress:
                continue
            _assign_item_to_worker(worker_id, item, in_progress)
            assigned_count += 1

        # 4) Drenar itens stale (travados ha mais de 10min)
        for serial, item in list(in_progress.items()):
            started = item.get("_started_at", "")
            if not started:
                continue
            try:
                t = datetime.fromisoformat(started).timestamp()
            except Exception:
                continue
            if now - t > STALE_ITEM_SECONDS:
                in_progress.pop(serial)
                queue.insert(0, item)
                stale_count += 1
                log(f"Stale drenado: {serial}")

        # 5) Salvar queue
        data["queue"] = queue
        data["in_progress"] = in_progress
        data["completed"] = completed
        data["failed"] = failed
        data["retry_count"] = retry_count
        save_queue(data)
    finally:
        file_unlock(fl)

    # 6) Atualizar dl_progress.json
    dl_progress = {}
    for worker_id, st in states.items():
        if st.get("type") != "downloader":
            continue
        serial = st.get("serial", "")
        if not serial:
            continue
        dl_progress[serial] = {
            "site": st.get("site", ""),
            "url": st.get("url", ""),
            "total": st.get("total", 0),
            "downloaded": st.get("downloaded", 0),
            "speed": st.get("speed", 0),
            "ts": st.get("ts", now),
        }
    save_dl_progress(dl_progress)

    return len(states), completed_now, failed_now, stale_count, assigned_count


def main_loop():
    log("Robot iniciado")
    while True:
        try:
            n, c, f, s, a = robot_cycle()
            log(f"Workers={n} completados={c} falhos={f} stale={s} atribuidos={a}")
            cleanup_old_worker_files(600)
        except Exception as e:
            log(f"Erro no ciclo: {e}")
        time.sleep(2)


if __name__ == "__main__":
    main_loop()
