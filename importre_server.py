#!/usr/bin/env python3
# pylint: disable=broad-except,bare-except,missing-function-docstring,missing-class-docstring,invalid-name,too-many-statements,too-many-branches,too-many-locals
"""Servidor HTTP standalone para o importre — nao importa Playwright.
Rodado como subprocesso para sobreviver ao ThreadPoolExecutor."""
import os
import json
import time
import logging
import threading
import urllib.parse
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
QUEUE_PATH = STATE_DIR / "queue.json"
SITES_PATH = STATE_DIR / "sites.json"
BLACKLIST_PATH = STATE_DIR / "blacklist.json"
CONTROL_PATH = STATE_DIR / "control.json"
LEARN_PATH = STATE_DIR / "learning.json"
DASHBOARD_PATH = STATE_DIR / "dashboard.html"
LOG_PATH = STATE_DIR / "importre.log"
COVERS_DIR = Path(os.path.expandvars(r"%USERPROFILE%\Documents\DuckStation\covers"))
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8765

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SRV] [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8")],
)
log = logging.getLogger("server")


def load_json(path, default):
    if path.exists():
        for attempt in range(3):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log.debug(f"load_json error {path}: {e}")
                time.sleep(0.05)
    return default


def save_json(path, data):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, str(path))


# ============================================================
# CACHE AGRESSIVO — múltiplos níveis
# ============================================================

class TimedCache:
    """Cache com TTL por chave."""
    def __init__(self, ttl=0.5):
        self.ttl = ttl
        self._data = {}
        self._ts = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            now = time.time()
            if key in self._data and now - self._ts[key] < self.ttl:
                return self._data[key]
            return None

    def set(self, key, value):
        with self._lock:
            self._data[key] = value
            self._ts[key] = time.time()

    def invalidate(self, key=None):
        with self._lock:
            if key:
                self._data.pop(key, None)
                self._ts.pop(key, None)
            else:
                self._data.clear()
                self._ts.clear()


# Caches com TTL diferentes para cada tipo de dado
_cache_queue = TimedCache(ttl=0.4)       # queue.json — muda rapidamente
_cache_sites = TimedCache(ttl=5.0)       # sites.json — muda raramente
_cache_blacklist = TimedCache(ttl=5.0)   # blacklist — muda raramente
_cache_control = TimedCache(ttl=0.5)     # control.json — muda pouco
_cache_learning = TimedCache(ttl=3.0)    # learning.json — muda ocasionalmente
_cache_dl_progress = TimedCache(ttl=0.15) # dl_progress.json — muda muito rápido
_cache_buffer = TimedCache(ttl=0.3)      # search_buffer.json
_cache_covers = TimedCache(ttl=15.0)     # covers dir scan — muito lento
_cache_status = TimedCache(ttl=0.2)      # status completo — resposta combinada


def load_dl_progress():
    cached = _cache_dl_progress.get("dl")
    if cached is not None:
        return cached
    data = load_json(STATE_DIR / "dl_progress.json", {})
    _cache_dl_progress.set("dl", data)
    return data


def load_sites():
    cached = _cache_sites.get("sites")
    if cached is not None:
        return cached
    data = load_json(SITES_PATH, {})
    _cache_sites.set("sites", data)
    return data


def save_sites(sites):
    save_json(SITES_PATH, sites)
    _cache_sites.invalidate()


def load_blacklist():
    cached = _cache_blacklist.get("bl")
    if cached is not None:
        return cached
    data = load_json(BLACKLIST_PATH, {"sites": []})
    _cache_blacklist.set("bl", data)
    return data


def load_control():
    cached = _cache_control.get("ctrl")
    if cached is not None:
        return cached
    data = load_json(CONTROL_PATH, {"action": "", "paused": False})
    _cache_control.set("ctrl", data)
    return data


def load_learning():
    cached = _cache_learning.get("learn")
    if cached is not None:
        return cached
    data = load_json(LEARN_PATH, {"site_stats": {}, "site_order": []})
    _cache_learning.set("learn", data)
    return data


def save_control(action="", paused=False):
    save_json(CONTROL_PATH, {"action": action, "paused": paused, "timestamp": time.time()})
    _cache_control.invalidate()


def clear_control():
    save_json(CONTROL_PATH, {"action": "", "paused": False, "timestamp": time.time()})
    _cache_control.invalidate()


def load_buffer():
    cached = _cache_buffer.get("buf")
    if cached is not None:
        return cached
    data = load_json(STATE_DIR / "search_buffer.json", {})
    _cache_buffer.set("buf", data)
    return data


def get_cover_count():
    cached = _cache_covers.get("count")
    if cached is not None:
        return cached
    try:
        count = len(list(COVERS_DIR.glob("*.jpg")))
    except Exception:
        count = 0
    _cache_covers.set("count", count)
    return count


def check_covers(serials):
    """Verifica quais serials têm capa, com cache individual."""
    result = {}
    for serial in serials:
        cached = _cache_covers.get(f"cover_{serial}")
        if cached is not None:
            result[serial] = cached
        else:
            exists = (COVERS_DIR / f"{serial}.jpg").exists()
            _cache_covers.set(f"cover_{serial}", exists)
            result[serial] = exists
    return result


def queue_get_status():
    """Retorna status da fila com cache agressivo."""
    cached = _cache_status.get("status")
    if cached is not None:
        return cached

    data = load_json(QUEUE_PATH, {"queue": [], "in_progress": {}, "completed": {}, "failed": {}, "retry_count": {}, "total": 0, "skipped": 0})
    queue = data.get("queue", [])
    in_prog = data.get("in_progress", {})
    completed = data.get("completed", {})
    failed = data.get("failed", {})
    if isinstance(completed, list):
        completed_count = len(completed)
        completed_items = {}
    else:
        completed_count = len(completed)
        completed_items = dict(list(sorted(completed.items(), key=lambda x: str(x[1].get("timestamp", x[1].get("completed_at", ""))), reverse=True)[:200])) if isinstance(next(iter(completed.values()), None), dict) else {}
    failed_count = len(failed) if isinstance(failed, (list, dict)) else 0
    total = data.get("total", len(queue) + len(in_prog) + completed_count + failed_count)
    skipped = data.get("skipped", 0)
    buf = load_buffer()
    buf_searching = sum(1 for v in buf.values() if isinstance(v, dict) and v.get("type") == "searching")
    buf_ready = sum(1 for v in buf.values() if isinstance(v, dict) and v.get("type") != "searching" and v.get("url"))
    searching_items = {}
    for serial, v in buf.items():
        if isinstance(v, dict) and v.get("type") == "searching":
            item_name = ""
            for q in queue:
                if isinstance(q, dict) and q.get("serial") == serial:
                    item_name = q.get("name", "")
                    break
            searching_items[serial] = {
                "name": item_name,
                "_phase": "searching",
                "_current_site": v.get("site", ""),
                "_detail": v.get("detail", ""),
            }
    busy_sites = {}
    for v in in_prog.values():
        site = v.get("_current_site", "")
        if site:
            busy_sites[site] = busy_sites.get(site, 0) + 1
    for v in buf.values():
        if isinstance(v, dict) and v.get("type") not in ("searching", "failed") and v.get("url"):
            site = v.get("site", "")
            if site:
                busy_sites[site] = busy_sites.get(site, 0) + 1
    result = {
        "total": total,
        "skipped": skipped,
        "pending": len(queue),
        "in_progress": len(in_prog) + buf_searching,
        "completed": completed_count,
        "failed": failed_count,
        "searching": sum(1 for v in in_prog.values() if v.get("_phase") == "searching") + buf_searching,
        "starting": sum(1 for v in in_prog.values() if v.get("_phase") == "starting"),
        "downloading": sum(1 for v in in_prog.values() if v.get("_phase") == "downloading"),
        "verifying": sum(1 for v in in_prog.values() if v.get("_phase") == "verifying"),
        "buffer_ready": buf_ready,
        "queue": queue[:20],
        "in_progress_items": {**searching_items, **in_prog},
        "completed_items": completed_items,
        "failed_items": failed,
        "dl_progress": load_dl_progress(),
        "busy_sites": busy_sites,
    }
    _cache_status.set("status", result)
    return result


def generate_dashboard_html():
    if DASHBOARD_PATH.exists():
        with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<html><body><h1>Dashboard nao gerado</h1></body></html>"


def run(port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, data, code=200):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

        def _html(self, content):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path

            if path in ("/", "/dashboard"):
                self._html(generate_dashboard_html())
                return

            if path == "/api/status":
                status = queue_get_status()
                sites = load_sites()
                bl = load_blacklist()
                ctrl = load_control()
                learn = load_learning()
                in_prog = status["in_progress"]
                if ctrl.get("action") == "stop":
                    proc_state = "stopped"
                elif ctrl.get("paused") or ctrl.get("action") == "pause":
                    proc_state = "paused"
                elif in_prog > 0:
                    proc_state = "running"
                elif status["pending"] > 0:
                    proc_state = "running"
                else:
                    proc_state = "idle"
                cover_count = get_cover_count()
                completed = status.get("completed_items", {})
                covers_info = check_covers(list(completed.keys()))
                self._json({
                    "status": status,
                    "sites": sites,
                    "blacklist": bl,
                    "control": ctrl,
                    "learning": learn,
                    "process_state": proc_state,
                    "server_online": True,
                    "cover_count": cover_count,
                    "covers_info": covers_info,
                    "server_time": time.time(),
                })
                return

            # Endpoint leve — só dl_progress + in_progress (para polling rápido)
            if path == "/api/status/fast":
                status = queue_get_status()
                self._json({
                    "status": {
                        "dl_progress": status["dl_progress"],
                        "in_progress_items": status["in_progress_items"],
                        "in_progress": status["in_progress"],
                        "pending": status["pending"],
                        "completed": status["completed"],
                        "failed": status["failed"],
                        "searching": status["searching"],
                        "starting": status["starting"],
                        "downloading": status["downloading"],
                        "verifying": status["verifying"],
                        "total": status["total"],
                        "busy_sites": status["busy_sites"],
                    },
                    "server_time": time.time(),
                })
                return

            # Endpoint para dados do emergency downloader (erros + log)
            if path == "/api/emergency":
                errors = load_json(STATE_DIR / "download_errors.json", {})
                dl_log = load_json(STATE_DIR / "emergency_download_log.json", {})
                # Ler queue.json para stats completas
                qdata = load_json(QUEUE_PATH, {})
                q_completed = qdata.get("completed", {})
                q_failed = qdata.get("failed", {})
                q_queue = qdata.get("queue", [])
                q_inprog = qdata.get("in_progress", {})
                self._json({
                    "errors": errors,
                    "dl_log": dl_log,
                    "queue_completed_count": len(q_completed) if isinstance(q_completed, dict) else 0,
                    "queue_failed_count": len(q_failed) if isinstance(q_failed, dict) else 0,
                    "queue_pending_count": len(q_queue) if isinstance(q_queue, list) else 0,
                    "queue_inprogress_count": len(q_inprog) if isinstance(q_inprog, dict) else 0,
                    "server_time": time.time(),
                })
                return

            if path == "/api/control/start":
                save_control(action="start", paused=False)
                self._json({"ok": True})
                return
            if path == "/api/control/pause":
                save_control(action="pause", paused=True)
                self._json({"ok": True})
                return
            if path == "/api/control/restart":
                save_control(action="restart", paused=False)
                self._json({"ok": True})
                return
            if path == "/api/control/stop":
                save_control(action="stop", paused=False)
                self._json({"ok": True})
                return
            if path == "/api/control/clear":
                clear_control()
                self._json({"ok": True})
                return

            # === Gerenciamento de sites ===
            if path.startswith("/api/sites/add"):
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                key = qs.get("key", [""])[0]
                site_url = qs.get("url", [""])[0]
                search_url = qs.get("search_url", [""])[0]
                if not key:
                    self._json({"ok": False, "error": "key required"})
                    return
                sites = load_sites()
                sites[key] = {
                    "url": site_url,
                    "search_url": search_url or site_url + "/?s={query}",
                    "type": "direct_search",
                    "enabled": True,
                    "fail_count": 0,
                    "max_fails": 50,
                }
                save_sites(sites)
                log.info(f"Site adicionado: {key} -> {site_url}")
                self._json({"ok": True, "key": key})
                return

            if path.startswith("/api/sites/remove"):
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                key = qs.get("key", [""])[0]
                if not key:
                    self._json({"ok": False, "error": "key required"})
                    return
                sites = load_sites()
                if key in sites:
                    del sites[key]
                    save_sites(sites)
                    log.info(f"Site removido: {key}")
                    self._json({"ok": True, "key": key})
                else:
                    self._json({"ok": False, "error": "not found"})
                return

            if path.startswith("/api/sites/toggle"):
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                key = qs.get("key", [""])[0]
                if not key:
                    self._json({"ok": False, "error": "key required"})
                    return
                sites = load_sites()
                if key in sites:
                    sites[key]["enabled"] = not sites[key].get("enabled", True)
                    save_sites(sites)
                    log.info(f"Site toggle: {key} -> enabled={sites[key]['enabled']}")
                    self._json({"ok": True, "key": key, "enabled": sites[key]["enabled"]})
                else:
                    self._json({"ok": False, "error": "not found"})
                return

            if path.startswith("/api/blacklist/clear"):
                save_json(BLACKLIST_PATH, {"sites": [], "urls": [], "archive_ids": [], "reasons": {}})
                _cache_blacklist.invalidate()
                log.info("Blacklist limpa")
                self._json({"ok": True})
                return

            self.send_response(404)
            self.end_headers()

    try:
        srv = ThreadingHTTPServer((SERVER_HOST, port), Handler)
        srv.daemon_threads = True
        log.info(f"Servidor bind: {SERVER_HOST}:{port}")
        srv.serve_forever()
    except Exception as e:
        log.warning(f"Erro servidor: {e}")


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else SERVER_PORT
    run(port)
