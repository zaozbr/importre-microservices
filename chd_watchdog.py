"""
Watchdog robusto para _chd_convert_v2.py.
- Reinicia o conversor se morrer ou travar.
- Detecta chdman preso (log inativo por muito tempo, CPU zero).
- Limpa CHDs invalidos (0/124 bytes) em F:\chd_temp.
- Le log, move .cue com falha irrecuperavel para duplicados e adiciona serial a fila de download.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

PSX_DIR = Path(r"D:\roms\library\roms\psx")
CHD_TEMP = Path(r"F:\chd_temp")
QUEUE_PATH = Path(r"D:\roms\library\roms\_importre_state\queue.json")
PYTHON = sys.executable
CHECK_INTERVAL = 60
STALE_LOG_THRESHOLD = 600  # 10 min sem novo output no log = travado
CHDMAN_MAX_IDLE = 3600     # 1h sem output = travado
LOCK_PATH = PSX_DIR / "_chd_convert.lock"
LOG_PATH = PSX_DIR / "_chd_convert.log"
WD_LOG_PATH = PSX_DIR / "chd_watchdog.log"
DUP_DIR = PSX_DIR / "duplicados"

# Regex para capturar nome do .cue de falhas
FAIL_CUE_RE = re.compile(
    r'FAIL\s*:.*?Error parsing input file \((?P<path>[^)]+\.cue)',
    re.IGNORECASE | re.DOTALL
)
SERIAL_RE = re.compile(
    r'(SLUS|SLES|SCES|SLPS|SLPM|SCPS|SCUS|SLKA|SCED|SIPS|PAPX|SLED|PCPX|PBPX|SCZS|SCPM|ESPM|PUPX|PTPX|PEPX|SCAJ|PCPD|PSRM|NYMC)[-_]?(\d{4,5})',
    re.I
)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    try:
        with open(WD_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def find_converter_pids():
    pids = []
    if not HAS_PSUTIL:
        return pids
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cl = ' '.join(p.info['cmdline'] or [])
            if '_chd_convert_v2.py' in cl.lower():
                pids.append(p.info['pid'])
        except Exception:
            pass
    return pids


def find_chdman_pids():
    pids = []
    if not HAS_PSUTIL:
        return pids
    for p in psutil.process_iter(['pid', 'name']):
        try:
            if p.info['name'] and 'chdman' in p.info['name'].lower():
                pids.append(p.info['pid'])
        except Exception:
            pass
    return pids


def kill_pid(pid):
    if HAS_PSUTIL:
        try:
            psutil.Process(pid).kill()
            return
        except Exception:
            pass
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], timeout=10)
    except Exception:
        pass


def kill_all_chdman():
    for pid in find_chdman_pids():
        log(f"Matando chdman PID={pid}")
        kill_pid(pid)


def start_converter():
    # Limpar lock
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass
    cmd = [PYTHON, "_chd_convert_v2.py", "--workers", "4"]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PSX_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x00000008 | 0x00000200 | 0x08000000,
            close_fds=True
        )
        log(f"_chd_convert_v2.py iniciado PID={proc.pid}")
        return proc.pid
    except Exception as e:
        log(f"Erro ao iniciar conversor: {e}")
        return None


def read_log_tail(n=20):
    try:
        if not LOG_PATH.exists():
            return []
        text = LOG_PATH.read_text(encoding="utf-8", errors="ignore")
        return text.splitlines()[-n:]
    except Exception:
        return []


def last_log_timestamp():
    # Usa mtime do arquivo de log
    try:
        return os.path.getmtime(LOG_PATH)
    except Exception:
        return 0


def clean_invalid_chds():
    removed = 0
    try:
        for f in CHD_TEMP.glob("*.chd"):
            try:
                size = f.stat().st_size
                if size < 1024:
                    f.unlink()
                    removed += 1
                    log(f"CHD invalido removido: {f.name} ({size} bytes)")
            except Exception:
                pass
    except Exception:
        pass
    return removed


def load_queue():
    try:
        return json.load(open(QUEUE_PATH, encoding="utf-8"))
    except Exception:
        return {"queue": [], "completed": {}, "in_progress": {}, "skipped": 0}


def save_queue(q):
    try:
        q['total'] = len(q.get('queue', [])) + len(q.get('completed', {})) + len(q.get('in_progress', {})) + q.get('skipped', 0)
        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
            json.dump(q, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Erro ao salvar fila: {e}")


def extract_serial(text):
    m = SERIAL_RE.search(text)
    if m:
        return f"{m.group(1).upper()}-{m.group(2).zfill(5)}"
    return None


def handle_failed_cues():
    """Le log, identifica .cue que falharam e move/adiciona a fila."""
    q = load_queue()
    existing = set()
    for item in q.get('queue', []):
        existing.add(item['serial'])
    existing.update(q.get('completed', {}).keys())
    existing.update(q.get('in_progress', {}).keys())

    lines = read_log_tail(200)
    moved = 0
    added = 0
    for line in lines:
        m = FAIL_CUE_RE.search(line)
        if not m:
            continue
        cue_path = Path(m.group('path').strip())
        if not cue_path.exists():
            continue
        # Ja movido?
        if cue_path.parent.name == 'duplicados':
            continue
        # Obter serial
        serial = extract_serial(cue_path.name) or extract_serial(cue_path.read_text(encoding='utf-8', errors='ignore'))
        # Mover para duplicados
        DUP_DIR.mkdir(exist_ok=True)
        dest = DUP_DIR / cue_path.name
        try:
            shutil.move(str(cue_path), str(dest))
            moved += 1
            log(f"Falha irrecuperavel: movido {cue_path.name} -> duplicados")
        except Exception as e:
            log(f"Erro ao mover {cue_path.name}: {e}")
            continue
        # Adicionar a fila
        if serial and serial not in existing:
            region = "JP" if serial.startswith(("SLPS", "SLPM", "SCPS")) else \
                     "EU" if serial.startswith(("SLES", "SCES")) else "US"
            q['queue'].append({
                'serial': serial,
                'name': cue_path.stem,
                'region': region,
                'section': '',
                'type': 'commercial',
                '_needs_search': True,
                '_phase': 'downloading',
                '_detail': 're-download: chd conversion failure',
            })
            existing.add(serial)
            added += 1
            log(f"Adicionado a fila de download: {serial} - {cue_path.stem}")
        elif not serial:
            log(f"SEM SERIAL: {cue_path.name} nao adicionado a fila")
    if moved or added:
        save_queue(q)
    return moved, added


def is_chdman_stuck():
    """Detecta chdman preso: log inativo por muito tempo ou CPU zero."""
    if not HAS_PSUTIL:
        return False
    last_ts = last_log_timestamp()
    age = time.time() - last_ts
    if age > CHDMAN_MAX_IDLE:
        return True
    chdmans = find_chdman_pids()
    if not chdmans:
        return False
    # Se chdman existe mas log nao muda ha STALE_LOG_THRESHOLD
    if age > STALE_LOG_THRESHOLD:
        return True
    # Se todos os chdman tem 0% CPU ha mais de 5 min
    zero_cpu_count = 0
    for pid in chdmans:
        try:
            proc = psutil.Process(pid)
            cpu = proc.cpu_percent(interval=0.5)
            if cpu < 0.5:
                zero_cpu_count += 1
        except Exception:
            pass
    if zero_cpu_count == len(chdmans) and len(chdmans) > 0:
        return True
    return False


def main():
    log("=== CHD Watchdog iniciado ===")
    while True:
        try:
            # Limpar CHDs invalidos
            clean_invalid_chds()

            # Lidar com falhas no log
            handle_failed_cues()

            # Verificar se conversor esta rodando
            pids = find_converter_pids()
            need_start = False
            if not pids:
                log("Conversor morto — reiniciando")
                need_start = True
            elif is_chdman_stuck():
                log("chdman travado — matando e reiniciando conversor")
                for pid in pids:
                    kill_pid(pid)
                kill_all_chdman()
                need_start = True
            else:
                log(f"Conversor OK: PID={pids[0]}")

            if need_start:
                kill_all_chdman()
                start_converter()

        except Exception as e:
            log(f"Erro no watchdog: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            log("Interrompido")
            break
        except Exception as e:
            log(f"FATAL: {e}")
            time.sleep(10)
