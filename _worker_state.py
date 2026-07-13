"""_worker_state.py — estado local por worker.

Cada worker (downloader/searcher) escreve APENAS no seu proprio arquivo JSON.
O _queue_robot.py e o unico processo que le esses arquivos e atualiza a fila central.

Isso elimina contenção entre workers e corrupção do queue.json/dl_progress.json.
"""
import json
import os
import time
from pathlib import Path
from datetime import datetime

STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
WORKERS_DIR = STATE_DIR / "workers"
EVENTS_DIR = STATE_DIR / "events"
WORKERS_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_DIR.mkdir(parents=True, exist_ok=True)


def _worker_path(worker_id):
    return WORKERS_DIR / f"{worker_id}.json"


def _atomic_write(path, data):
    tmp = str(path) + ".tmp"
    for attempt in range(5):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, str(path))
            return
        except (OSError, PermissionError):
            time.sleep(0.05 * (attempt + 1))
    # ultimo recurso: tentar escrever direto
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_worker_state(worker_id, default=None):
    path = _worker_path(worker_id)
    if not path.exists():
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def save_worker_state(worker_id, data):
    path = _worker_path(worker_id)
    data["_updated_at"] = time.time()
    data["_updated_at_iso"] = datetime.now().isoformat()
    _atomic_write(path, data)


def update_worker_state(worker_id, **kwargs):
    state = load_worker_state(worker_id)
    state.update(kwargs)
    save_worker_state(worker_id, state)


def set_worker_download(worker_id, serial, site, url, total, downloaded, speed, phase="downloading", detail=""):
    state = load_worker_state(worker_id)
    state["type"] = "downloader"
    state["serial"] = serial
    state["site"] = site
    state["url"] = url[:200] if url else ""
    state["total"] = total
    state["downloaded"] = downloaded
    state["speed"] = speed
    state["phase"] = phase
    state["detail"] = detail[:200]
    state["ts"] = time.time()
    save_worker_state(worker_id, state)


def set_worker_search(worker_id, serial, site, phase="searching", detail=""):
    state = load_worker_state(worker_id)
    state["type"] = "searcher"
    state["serial"] = serial
    state["site"] = site
    state["phase"] = phase
    state["detail"] = detail[:200]
    state["ts"] = time.time()
    save_worker_state(worker_id, state)


def set_worker_idle(worker_id):
    state = load_worker_state(worker_id)
    state["type"] = "idle"
    state["phase"] = "idle"
    state["serial"] = ""
    state["site"] = ""
    state["ts"] = time.time()
    save_worker_state(worker_id, state)


def get_all_worker_states():
    states = {}
    for path in WORKERS_DIR.glob("*.json"):
        if path.name.endswith(".tmp"):
            continue
        worker_id = path.stem
        states[worker_id] = load_worker_state(worker_id)
    return states


def post_event(event_type, worker_id, serial, site="", detail="", extra=None):
    """Posta um evento para o robot processar. event_type: 'completed', 'failed', 'stuck'."""
    event = {
        "event": event_type,
        "worker_id": worker_id,
        "serial": serial,
        "site": site,
        "detail": detail[:500],
        "ts": time.time(),
        "extra": extra or {},
    }
    path = EVENTS_DIR / f"{event_type}_{worker_id}_{serial}_{int(time.time()*1000)}.json"
    _atomic_write(path, event)


def get_pending_events():
    events = []
    for path in sorted(EVENTS_DIR.glob("*.json")):
        if path.name.endswith(".tmp"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                events.append(json.load(f))
        except Exception:
            pass
    return events


def ack_event(path_or_event):
    if isinstance(path_or_event, dict):
        event = path_or_event
        ts = event.get("ts", 0)
        worker_id = event.get("worker_id", "")
        serial = event.get("serial", "")
        event_type = event.get("event", "")
        path = EVENTS_DIR / f"{event_type}_{worker_id}_{serial}_{int(ts*1000)}.json"
    else:
        path = Path(path_or_event)
    try:
        path.unlink()
    except Exception:
        pass


def cleanup_old_worker_files(max_age_seconds=300):
    now = time.time()
    removed = 0
    for path in WORKERS_DIR.glob("*.json"):
        if path.name.endswith(".tmp"):
            continue
        try:
            st = path.stat()
            if now - st.st_mtime > max_age_seconds:
                path.unlink()
                removed += 1
        except Exception:
            pass
    return removed
