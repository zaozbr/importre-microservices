"""
Watchdog autônomo v3 — sem wmic, apenas API e subprocess.
Robusto para pythonw.exe em background.
"""
import json, os, sys, time, subprocess, shutil
from pathlib import Path
from datetime import datetime

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except:
    pass
try:
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

PSX_DIR = Path(r'D:\roms\library\roms\psx')
STATE_DIR = Path(r'D:\roms\library\roms\_importre_state')
QUEUE_FILE = STATE_DIR / 'queue.json'
LOG_FILE = STATE_DIR / 'watchdog_autonomous.log'
CHD_TEMP = Path(r'F:\chd_temp')
CHD_DEST = Path(r'D:\roms\library\roms\psx')
DOWNLOADS_TMP = Path(r'D:\roms\library\roms\psx\_downloads_tmp')
IMPORTRE = PSX_DIR / 'importre.py'
CHD_CONVERT = PSX_DIR / '_chd_convert_v2.py'
ARIA2_MANAGER = PSX_DIR / '_aria2_manager.py'
WORKERS = 8
CHECK_INTERVAL = 60

last_completed = 0
last_failed = 0
speed_stall_count = 0
importre_restarts = 0
chds_moved_total = 0

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    try:
        print(line, flush=True)
    except:
        pass
    try:
        with open(LOG_FILE, 'a', encoding='utf-8', errors='replace') as f:
            f.write(line + '\n')
    except:
        pass

def api_status():
    try:
        import urllib.request
        r = urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=10)
        return json.loads(r.read().decode('utf-8', errors='replace'))
    except:
        return None

def is_aria2_running():
    """Verifica se o daemon aria2c está rodando via RPC (porta 6801)."""
    try:
        import urllib.request
        payload = json.dumps({
            "jsonrpc": "2.0", "id": "wd",
            "method": "aria2.getVersion",
            "params": ["token:psx_download_2026"],
        }).encode('utf-8')
        req = urllib.request.Request(
            'http://localhost:6801/jsonrpc',
            data=payload,
            headers={'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return 'result' in data
    except:
        return False

def start_aria2():
    """Inicia o daemon aria2c via _aria2_manager.py."""
    try:
        subprocess.Popen(
            [PYTHONW, str(ARIA2_MANAGER), 'start'],
            cwd=str(PSX_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
        )
        log('aria2c daemon iniciado via _aria2_manager.py')
    except Exception as e:
        log(f'ERRO ao iniciar aria2c: {e}')

PYTHONW = r"C:\Users\Usuario\AppData\Local\Programs\Python\Python314\python.exe"

def is_importre_running():
    """Verifica se importre.py (com workers) está rodando.
    Usa wmic para checar processo python rodando importre.py (não importre_server.py).
    Fallback: se wmic falhar, usar API + atividade de downloads."""
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where',
             "commandline like '%importre.py%' and not commandline like '%importre_server%' and not commandline like '%_watchdog%' and not commandline like '%wmic%'",
             'get', 'ProcessId'],
            capture_output=True, text=True, timeout=10)
        pids = [l.strip() for l in result.stdout.split('\n') if l.strip().isdigit()]
        if len(pids) > 0:
            return True
    except:
        pass
    # Fallback: se wmic não encontrar, verificar via API se há atividade
    data = api_status()
    if data:
        s = data.get('status', {})
        ip = s.get('in_progress', 0)
        dl = s.get('downloading', 0)
        # Se há itens em progresso ou downloads ativos, o importre está rodando
        if ip > 0 or dl > 0:
            return True
    return False

def start_importre():
    global importre_restarts
    try:
        subprocess.Popen(
            [PYTHONW, str(IMPORTRE), '--workers', str(WORKERS),
             '--rounds', '999', '--limit', '999', '--no-server'],
            cwd=str(PSX_DIR.parent),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        importre_restarts += 1
        log(f'importre.py iniciado ({WORKERS} workers) — restart #{importre_restarts}')
    except Exception as e:
        log(f'ERRO ao iniciar importre: {e}')
    try:
        q = json.load(open(QUEUE_FILE, 'r', encoding='utf-8'))
        ip = q.get('in_progress', {})
        queue = q.get('queue', [])
        if len(ip) == 0:
            return 0
        for serial, item in ip.items():
            if isinstance(item, dict):
                for key in ['_phase', '_current_site', '_detail', '_lock_ts', '_started_at']:
                    item.pop(key, None)
                queue.append(item)
        q['queue'] = queue
        q['in_progress'] = {}
        q['total'] = len(queue) + len(q.get('completed', {})) + len(q.get('failed', {}))
        json.dump(q, open(QUEUE_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        log(f'Drenado {len(ip)} itens de in_progress')
        return len(ip)
    except Exception as e:
        log(f'ERRO ao drenar: {e}')
        return 0

def move_chds_from_temp():
    global chds_moved_total
    if not CHD_TEMP.exists():
        return
    try:
        chds = list(CHD_TEMP.glob('*.chd'))
        moved = 0
        for chd in chds:
            dst = CHD_DEST / chd.name
            try:
                if dst.exists() and dst.stat().st_size >= chd.stat().st_size:
                    chd.unlink()
                    continue
                shutil.move(str(chd), str(dst))
                moved += 1
            except:
                pass
        if moved > 0:
            chds_moved_total += moved
            log(f'Movidos {moved} CHDs (total: {chds_moved_total})')
    except:
        pass

def check_downloads_tmp():
    if not DOWNLOADS_TMP.exists():
        return 0
    try:
        count = 0
        for f in DOWNLOADS_TMP.iterdir():
            if f.is_file() and f.suffix.lower() in ['.7z', '.zip', '.rar', '.bin', '.img', '.iso', '.ecm', '.mdf', '.chd']:
                count += 1
        return count
    except:
        return 0

def start_chd_convert():
    if not CHD_CONVERT.exists():
        return
    try:
        subprocess.Popen(
            [sys.executable, str(CHD_CONVERT)],
            cwd=str(PSX_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        log('Conversor CHD iniciado')
    except:
        pass

def report_status(data):
    global last_completed, last_failed
    try:
        s = data.get('status', {})
        pending = s.get('pending', 0)
        in_progress = s.get('in_progress', 0)
        completed = s.get('completed', 0)
        failed = s.get('failed', 0)
        downloading = s.get('downloading', 0)
        dl = s.get('dl_progress', {})
        total_speed = sum(p.get('speed', 0) for p in dl.values()) / 1e6
        chd_count = 0
        if CHD_TEMP.exists():
            try:
                chd_count = len(list(CHD_TEMP.glob('*.chd')))
            except:
                pass
        dl_count = check_downloads_tmp()
        new_completed = completed - last_completed
        new_failed = failed - last_failed
        last_completed = completed
        last_failed = failed
        emoji = '+' if total_speed >= 20 else ('~' if total_speed > 1 else '!')
        log(f'{emoji} pend={pending} ip={in_progress} dl={downloading} ok={completed} fail={failed} '
            f'speed={total_speed:.1f}MB/s chd_tmp={chd_count} dl_tmp={dl_count} '
            f'restarts={importre_restarts} moved={chds_moved_total}')
        if new_completed > 0:
            log(f'  >> {new_completed} novo(s) download(s) concluido(s)!')
        if new_failed > 0:
            log(f'  >> {new_failed} nova(s) falha(s)')
    except Exception as e:
        log(f'ERRO em report: {e}')

def run_single_cycle():
    """Executa um unico ciclo do watchdog e sai.
    O schtasks chama este script a cada 1 minuto.
    SEM time.sleep() — pythonw.exe trava com sleep em background."""
    log(f'--- Ciclo ---')

    # 1. Verificar importre
    if not is_importre_running():
        log('importre parado — reiniciando...')
        start_importre()
        # SEM time.sleep — o schtasks vai chamar de novo em 1 min

    # 2. Status
    data = api_status()
    if data:
        report_status(data)
        s = data.get('status', {})
        in_progress = s.get('in_progress', 0)
        downloading = s.get('downloading', 0)
        pending = s.get('pending', 0)
        dl = s.get('dl_progress', {})
        total_speed = sum(p.get('speed', 0) for p in dl.values()) / 1e6

        # 3. Estagnamento
        global speed_stall_count
        if in_progress > 0 and downloading == 0 and total_speed < 1:
            speed_stall_count += 1
            if speed_stall_count >= 5:
                log('ESTAGNADO — drenando e reiniciando')
                drain_inprogress()
                start_importre()
                speed_stall_count = 0
        else:
            speed_stall_count = 0

        # 4. Fila vazia
        if pending == 0 and in_progress == 0:
            log(f'FILA VAZIA! ok={s.get("completed",0)} fail={s.get("failed",0)}')

    # 5. Mover CHDs
    move_chds_from_temp()

    # 6. Conversor CHD
    dl_count = check_downloads_tmp()
    if dl_count > 0:
        log(f'{dl_count} arquivos em _downloads_tmp')
        start_chd_convert()

    # 7. Disco
    for drive in ['C:', 'D:', 'F:']:
        try:
            usage = shutil.disk_usage(drive + '\\')
            if usage.free / 1e9 < 10:
                log(f'ALERTA: {drive} com {usage.free/1e9:.1f}GB livre!')
        except:
            pass


def main_loop():
    """Loop continuo — SEMPRE em loop mode."""
    import ctypes
    # Proteção contra instância única — mata watchdogs duplicados
    # NÃO matar no primeiro ciclo para evitar matar o processo pai (cmd)
    log('='*60)
    log('WATCHDOG v3 INICIADO — 9h unattended')
    log(f'Intervalo: {CHECK_INTERVAL}s | Workers: {WORKERS}')
    log(f'argv: {sys.argv}')
    log('='*60)

    cycle_count = 0
    while True:
        cycle_count += 1
        # A cada 5 ciclos, verificar duplicatas
        if cycle_count % 5 == 1 and cycle_count > 1:
            try:
                result = subprocess.run(
                    ['wmic', 'process', 'where',
                     "commandline like '%_watchdog_autonomous%' and not commandline like '%wmic%'",
                     'get', 'ProcessId'],
                    capture_output=True, text=True, timeout=10)
                pids = [int(l.strip()) for l in result.stdout.split('\n') if l.strip().isdigit()]
                my_pid = os.getpid()
                other_pids = [p for p in pids if p != my_pid]
                if other_pids:
                    log(f'MATANDO {len(other_pids)} watchdog(s) duplicado(s): {other_pids}')
                    for p in other_pids:
                        try:
                            subprocess.run(['taskkill', '/F', '/PID', str(p)],
                                         capture_output=True, timeout=5,
                                         creationflags=0x08000000)
                        except:
                            pass
            except:
                pass
        try:
            run_single_cycle_no_exit()
        except Exception as e:
            log(f'ERRO: {e}')
        # ctypes Sleep — chama kernel32.Sleep diretamente, ignora signals Python
        log(f'Sleeping {CHECK_INTERVAL}s...')
        ctypes.windll.kernel32.Sleep(CHECK_INTERVAL * 1000)
        log('Sleep concluido')


def run_single_cycle_no_exit():
    """Executa um ciclo sem os._exit — para uso em main_loop()."""
    log(f'--- Ciclo ---')

    # 0. Verificar aria2c daemon (essencial para downloads)
    if not is_aria2_running():
        log('aria2c daemon parado — reiniciando...')
        start_aria2()

    # 1. Verificar importre
    if not is_importre_running():
        log('importre parado — reiniciando...')
        start_importre()

    # 2. Status
    data = api_status()
    if data:
        report_status(data)
        s = data.get('status', {})
        in_progress = s.get('in_progress', 0)
        downloading = s.get('downloading', 0)
        pending = s.get('pending', 0)
        dl = s.get('dl_progress', {})
        total_speed = sum(p.get('speed', 0) for p in dl.values()) / 1e6

        global speed_stall_count
        if in_progress > 0 and downloading == 0 and total_speed < 1:
            speed_stall_count += 1
            if speed_stall_count >= 5:
                log('ESTAGNADO — drenando e reiniciando')
                drain_inprogress()
                start_importre()
                speed_stall_count = 0
        else:
            speed_stall_count = 0

        if pending == 0 and in_progress == 0:
            log(f'FILA VAZIA! ok={s.get("completed",0)} fail={s.get("failed",0)}')

    # 3. Mover CHDs
    move_chds_from_temp()

    # 4. Conversor CHD
    dl_count = check_downloads_tmp()
    if dl_count > 0:
        log(f'{dl_count} arquivos em _downloads_tmp')
        start_chd_convert()

    # 5. Disco
    for drive in ['C:', 'D:', 'F:']:
        try:
            usage = shutil.disk_usage(drive + '\\')
            if usage.free / 1e9 < 10:
                log(f'ALERTA: {drive} com {usage.free/1e9:.1f}GB livre!')
        except:
            pass

if __name__ == '__main__':
    main_loop()
