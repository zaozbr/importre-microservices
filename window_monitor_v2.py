#!/usr/bin/env python3
"""
window_monitor_v2.py — Monitor de janelas de terminal no Windows.

Objetivo: descobrir qual processo esta abrindo janelas de terminal/powershell/cmd/python
que roubam o foco e quebram a digitacao do usuario.

Restricoes:
- NAO mata processos.
- NAO para supervisores.
- Apenas monitora e loga.
- Intervalo minimo 500ms.

Log: D:\\roms\\library\\roms\\_importre_state\\window_monitor_v2.log
"""

import os
import sys
import json
import time
import ctypes
import ctypes.wintypes
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# ============================================================
# CONFIG
# ============================================================
STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
LOG_PATH = STATE_DIR / "window_monitor_v2.log"
PID_FILE = STATE_DIR / "window_monitor_v2.pid"

INTERVAL_MS = 750          # ms entre scans (>= 500ms)
INTERVAL = INTERVAL_MS / 1000.0
REPORT_INTERVAL_S = 300    # 5 minutos
FLASH_THRESHOLD_S = 3.0  # janelas que aparecem e somem em < 3s

SUSPICIOUS_NAMES = {"powershell.exe", "cmd.exe", "conhost.exe", "python.exe"}
SUSPICIOUS_TITLES = [
    "powershell", "cmd", "python", "select", "windows powershell",
    "command prompt", "terminal", "console"
]

# ============================================================
# LOGGING
# ============================================================
STATE_DIR.mkdir(parents=True, exist_ok=True)

class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            super().emit(record)
        except OSError:
            pass
    def flush(self):
        try:
            super().flush()
        except OSError:
            pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        SafeStreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("window_monitor_v2")

# ============================================================
# WIN32 API / CTYPEs
# ============================================================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll

# EnumWindows
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(
    ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
)

IsWindowVisible = user32.IsWindowVisible
GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextW = user32.GetWindowTextW
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowRect = user32.GetWindowRect

# Process query
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_BASIC_INFORMATION = 0

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

class PROCESS_BASIC_INFORMATION_STRUCT(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2", ctypes.c_void_p * 2),
        ("UniqueProcessId", ctypes.c_void_p),
        ("InheritedFromUniqueProcessId", ctypes.c_void_p),
    ]

OpenProcess = kernel32.OpenProcess
CloseHandle = kernel32.CloseHandle
NtQueryInformationProcess = ntdll.NtQueryInformationProcess

GetModuleFileNameExW = ctypes.windll.psapi.GetModuleFileNameExW
GetProcessImageFileNameW = ctypes.windll.psapi.GetProcessImageFileNameW

# ============================================================
# PSUTIL (fallback opcional, mas preferido para cmdline)
# ============================================================
try:
    import psutil
    HAS_PSUTIL = True
except Exception:
    HAS_PSUTIL = False

# ============================================================
# FUNCOES
# ============================================================
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def get_window_text(hwnd):
    try:
        length = GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def get_window_rect(hwnd):
    try:
        rect = RECT()
        if GetWindowRect(hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        pass
    return (0, 0, 0, 0)


def get_parent_pid(pid):
    """Retorna PPID via NtQueryInformationProcess."""
    try:
        hproc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not hproc:
            return None
        pbi = PROCESS_BASIC_INFORMATION_STRUCT()
        ret_len = ctypes.c_ulong(0)
        status = NtQueryInformationProcess(
            hproc,
            PROCESS_BASIC_INFORMATION,
            ctypes.byref(pbi),
            ctypes.sizeof(pbi),
            ctypes.byref(ret_len),
        )
        CloseHandle(hproc)
        if status == 0 and pbi.InheritedFromUniqueProcessId:
            return int(ctypes.cast(pbi.InheritedFromUniqueProcessId, ctypes.c_void_p).value)
    except Exception:
        pass
    # fallback psutil
    if HAS_PSUTIL:
        try:
            return psutil.Process(pid).ppid()
        except Exception:
            pass
    return None


def get_process_info(pid):
    """Retorna dict com nome, caminho, cmdline, ppid, parent_name, lifetime."""
    info = {
        "pid": pid,
        "name": None,
        "exe": None,
        "cmdline": None,
        "ppid": None,
        "parent_name": None,
        "lifetime_s": None,
        "create_time": None,
    }
    if not HAS_PSUTIL:
        # tenta obter nome pelo handle do processo (kernel32/ntdll)
        try:
            hproc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if hproc:
                buf = ctypes.create_unicode_buffer(1024)
                if GetProcessImageFileNameW(hproc, buf, 1024):
                    info["exe"] = buf.value
                    info["name"] = Path(buf.value).name
                CloseHandle(hproc)
        except Exception:
            pass
        info["ppid"] = get_parent_pid(pid)
        return info

    try:
        p = psutil.Process(pid)
        info["name"] = p.name()
        try:
            info["exe"] = p.exe()
        except Exception:
            info["exe"] = ""
        try:
            info["cmdline"] = " ".join(p.cmdline() or [])
        except Exception:
            info["cmdline"] = ""
        try:
            info["ppid"] = p.ppid()
        except Exception:
            info["ppid"] = get_parent_pid(pid)
        try:
            info["create_time"] = p.create_time()
            info["lifetime_s"] = int(time.time() - info["create_time"])
        except Exception:
            pass
    except Exception:
        info["ppid"] = get_parent_pid(pid)
        return info

    if info["ppid"]:
        try:
            parent = psutil.Process(info["ppid"])
            info["parent_name"] = parent.name()
        except Exception:
            pass
    return info


def is_suspicious(proc_info, title):
    """Heuristica de suspeita: nome/ titulo."""
    name = (proc_info.get("name") or "").lower()
    title_l = (title or "").lower()
    parent = (proc_info.get("parent_name") or "").lower()

    if name in SUSPICIOUS_NAMES:
        return True
    if parent in SUSPICIOUS_NAMES:
        return True
    for term in SUSPICIOUS_TITLES:
        if term in title_l:
            return True
    return False


def identify_python_script(proc_info):
    """Tenta extrair o script Python iniciador do cmdline."""
    cmd = proc_info.get("cmdline") or ""
    lower = cmd.lower()
    if "python" in lower or "pythonw" in lower:
        # tentar achar arquivo .py
        for part in cmd.split():
            if ".py" in part.lower():
                return part
    return None


def enum_visible_windows():
    """Retorna lista de dicts {hwnd, pid, title, rect, visible}."""
    results = []

    def callback(hwnd, extra):
        if not IsWindowVisible(hwnd):
            return True
        title = get_window_text(hwnd)
        pid = ctypes.wintypes.DWORD(0)
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pid_val = pid.value
        rect = get_window_rect(hwnd)
        results.append({
            "hwnd": hwnd,
            "pid": pid_val,
            "title": title,
            "rect": rect,
            "visible": True,
        })
        return True

    EnumWindows(EnumWindowsProc(callback), 0)
    return results


def format_window_log(w, proc_info, event_type):
    name = proc_info.get("name") or "?"
    exe = proc_info.get("exe") or "?"
    cmdline = proc_info.get("cmdline") or "?"
    ppid = proc_info.get("ppid") or "?"
    parent_name = proc_info.get("parent_name") or "?"
    lifetime = proc_info.get("lifetime_s")
    lifetime_str = f"{lifetime}s" if lifetime is not None else "?"
    x, y, wdt, hgt = w.get("rect") or (0, 0, 0, 0)
    script = identify_python_script(proc_info)
    script_str = f" | script={script}" if script else ""

    return (
        f"[{event_type}] ts={now_str()} hwnd={w['hwnd']} pid={w['pid']} name={name} "
        f"title={w['title']!r} exe={exe} cmdline={cmdline!r} "
        f"ppid={ppid} parent={parent_name} lifetime={lifetime_str} "
        f"rect=({x},{y} {wdt}x{hgt}){script_str}"
    )


def load_process_names_by_pid():
    """Cache rapido de nomes de processo via psutil."""
    cache = {}
    if not HAS_PSUTIL:
        return cache
    try:
        for p in psutil.process_iter(["pid", "name"]):
            try:
                cache[p.info["pid"]] = p.info["name"]
            except Exception:
                pass
    except Exception:
        pass
    return cache


def main():
    log.info("=== Window Monitor v2 iniciado ===")
    log.info(f"Log: {LOG_PATH}")
    log.info(f"Scan interval: {INTERVAL_MS}ms")

    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception as e:
        log.warning(f"Nao foi possivel salvar PID file: {e}")

    # Estado: hwnd -> {first_seen, last_seen, info, proc_info}
    windows = {}
    # pid -> process info cache
    proc_cache = {}

    last_report = time.time()
    stats = {
        "scans": 0,
        "visible_total": 0,
        "suspicious_seen": 0,
        "flash_events": 0,
        "started_at": datetime.now().isoformat(),
    }

    while True:
        loop_start = time.time()
        stats["scans"] += 1

        try:
            current_hwnds = set()
            visible_windows = enum_visible_windows()
            # cache de nomes para processos leves
            name_cache = load_process_names_by_pid() if HAS_PSUTIL else {}

            for w in visible_windows:
                hwnd = w["hwnd"]
                pid = w["pid"]
                current_hwnds.add(hwnd)

                # pular janelas sem titulo? O pedido diz verificar MainWindowTitle nao vazio
                # mas tambem monitorar visiveis. Vamos logar apenas se titulo nao vazio OU processo suspeito.
                if not w["title"] and pid not in proc_cache:
                    continue

                if pid not in proc_cache:
                    proc_cache[pid] = get_process_info(pid)
                proc_info = proc_cache[pid]
                name = proc_info.get("name") or name_cache.get(pid) or "?"
                proc_info["name"] = name

                if hwnd not in windows:
                    windows[hwnd] = {
                        "first_seen": time.time(),
                        "last_seen": time.time(),
                        "info": w,
                        "proc_info": proc_info,
                        "logged": False,
                    }
                    # Loga no arquivo apenas janelas de processos suspeitos (powershell, cmd, conhost, python)
                    # ou com titulo suspeito. Outras janelas vao apenas para debug (nao salvas no log).
                    if is_suspicious(proc_info, w["title"]):
                        stats["suspicious_seen"] += 1
                        log.warning(format_window_log(w, proc_info, "NEW_SUSPICIOUS"))
                        windows[hwnd]["logged"] = True
                    elif w["title"]:
                        log.debug(format_window_log(w, proc_info, "NEW_WINDOW"))
                else:
                    windows[hwnd]["last_seen"] = time.time()
                    windows[hwnd]["info"] = w

            # Detectar janelas que sumiram
            now = time.time()
            gone = [hwnd for hwnd in windows if hwnd not in current_hwnds]
            for hwnd in gone:
                data = windows.pop(hwnd)
                duration = now - data["first_seen"]
                w = data["info"]
                proc_info = data["proc_info"]
                if duration < FLASH_THRESHOLD_S and (data["logged"] or is_suspicious(proc_info, w["title"])):
                    stats["flash_events"] += 1
                    log.warning(
                        f"[FLASH] ts={now_str()} hwnd={hwnd} pid={w['pid']} "
                        f"title={w['title']!r} name={proc_info.get('name') or '?'} "
                        f"duration={duration:.2f}s ppid={proc_info.get('ppid') or '?'} "
                        f"parent={proc_info.get('parent_name') or '?'} "
                        f"cmdline={proc_info.get('cmdline') or '?'!r}"
                    )

            # Limpar cache de processos que nao existem mais
            if HAS_PSUTIL and stats["scans"] % 50 == 0:
                alive = set()
                try:
                    for p in psutil.process_iter(["pid"]):
                        alive.add(p.info["pid"])
                except Exception:
                    pass
                proc_cache = {pid: info for pid, info in proc_cache.items() if pid in alive}

            # Report a cada 5 min
            if time.time() - last_report >= REPORT_INTERVAL_S:
                last_report = time.time()
                uptime = int(time.time() - datetime.fromisoformat(stats["started_at"]).timestamp())
                report = (
                    f"[REPORT] ts={now_str()} uptime={uptime}s scans={stats['scans']} "
                    f"visible_windows_now={len(current_hwnds)} suspicious_seen={stats['suspicious_seen']} "
                    f"flash_events={stats['flash_events']}"
                )
                log.info(report)

        except Exception as e:
            log.exception(f"Erro no loop de scan: {e}")

        elapsed = time.time() - loop_start
        sleep_time = max(0.0, INTERVAL - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception(f"Monitor morreu: {e}")
        raise
