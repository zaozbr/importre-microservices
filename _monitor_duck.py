#!/usr/bin/env python3
"""Monitor perpétuo do teste DuckStation.
A cada 5 minutos:
- Verifica progresso do teste
- Verifica se o processo ainda está rodando (reinicia se morreu)
- Se CHDs falharam no teste, adiciona na fila do importre para re-download
- Move jogos com problema para d:\romspsxduplicas
- Loga resultados
"""
import sys, json, re, os, time, subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
DUP = PSX / "duplicados"
RESULTS_FILE = PSX / "_duck_test_results.json"
LOG_FILE = PSX / "_duck_monitor.log"
DUCK_TEST_LOG = PSX / "_duck_test.log"
QUEUE_FILE = Path(r"D:\roms\library\roms\_importre_state\queue.json")
DEST_DIR = Path(r"D:\roms\psxduplicas")
CHECK_INTERVAL = 300  # 5 minutos

def monitor_log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

def get_test_progress():
    """Le o log do teste e retorna (current, total, ok, fail, unk, deleted, bytes_freed)."""
    if not DUCK_TEST_LOG.exists():
        return None
    lines = DUCK_TEST_LOG.read_text(encoding='utf-8', errors='replace').strip().splitlines()
    if not lines:
        return None
    # Procurar ultima linha de progresso
    for line in reversed(lines):
        m = re.match(r'\[.*?\] \[(\d+)/(\d+)\]\s+(\w+)\s+\|\s+OK=(\d+)\s+FAIL=(\d+)\s+UNK=(\d+)\s+\|\s+ETA=\S+\s+\|\s+del=(\d+)\s+\(([\d.]+)GB\)', line)
        if m:
            return {
                'current': int(m.group(1)),
                'total': int(m.group(2)),
                'status': m.group(3),
                'ok': int(m.group(4)),
                'fail': int(m.group(5)),
                'unk': int(m.group(6)),
                'deleted': int(m.group(7)),
                'gb_freed': float(m.group(8)),
            }
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


def is_duck_test_running():
    """Verifica se o processo _duck_test.py esta rodando."""
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
            **get_run_kwargs(15)
        )
        for line in result.stdout.splitlines():
            if "_duck_test" in line:
                # Extrair PID
                parts = line.split(",")
                if len(parts) >= 2:
                    pid = parts[-1].strip()
                    return True, int(pid) if pid.isdigit() else None
        return False, None
    except Exception:
        return False, None

def restart_duck_test():
    """Reinicia o teste DuckStation em background."""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        subprocess.Popen(
            ["python", str(PSX / "_duck_test.py"), "--timeout", "12", "--workers", "1", "--resume"],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            startupinfo=startupinfo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        monitor_log("Teste DuckStation reiniciado!")
        return True
    except Exception as e:
        monitor_log(f"Erro ao reiniciar teste: {e}")
        return False

def add_fails_to_importre(failed_chds):
    """Adiciona CHDs que falharam no teste na fila do importre para re-download."""
    if not failed_chds:
        return 0
    try:
        sys.path.insert(0, str(PSX))
        from importre import file_lock, file_unlock, load_json, save_json, QUEUE_PATH
        fl = file_lock()
        try:
            data = load_json(QUEUE_PATH, {})
            added = 0
            existing = set()
            for q in data.get('queue', []):
                existing.add(q.get('serial', '').upper())
            for k in data.get('in_progress', {}).keys():
                existing.add(k.upper())
            for k in data.get('completed', {}).keys():
                existing.add(k.upper())
            for k in data.get('failed', {}).keys():
                existing.add(k.upper())

            for chd_path, detail in failed_chds:
                serial = extract_serial(Path(chd_path).name)
                if not serial:
                    continue
                if serial in existing:
                    continue
                data['queue'].append({
                    'serial': serial,
                    'name': Path(chd_path).stem,
                    'region': '',
                    'section': '',
                    'type': 'commercial',
                    '_needs_search': True,
                    '_fail_reason': detail[:100],
                })
                existing.add(serial)
                added += 1
            data['total'] = len(data.get('queue', [])) + len(data.get('in_progress', {})) + len(data.get('completed', {})) + len(data.get('failed', {}))
            save_json(QUEUE_PATH, data)
            return added
        finally:
            file_unlock(fl)
    except Exception as e:
        monitor_log(f"Erro ao adicionar falhas na fila: {e}")
        return 0

def move_failed_to_dest(failed_chds):
    """Move CHDs que falharam para d:\romspsxduplicas para re-download."""
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    moved = 0
    for chd_path, detail in failed_chds:
        src = Path(chd_path)
        if not src.exists():
            continue
        dst = DEST_DIR / src.name
        try:
            src.rename(dst)
            moved += 1
            monitor_log(f"  MOVIDO {src.name} -> {dst}")
        except Exception as e:
            monitor_log(f"  ERRO ao mover {src.name}: {e}")
    return moved

def check_new_fails():
    """Verifica resultados novos com FAIL e processa."""
    if not RESULTS_FILE.exists():
        return []
    try:
        results = json.loads(RESULTS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return []
    new_fails = []
    for path, info in results.items():
        if info.get('status') == 'FAIL':
            new_fails.append((path, info.get('detail', '')))
    return new_fails

def main():
    monitor_log("=" * 60)
    monitor_log("MONITOR PERPETUO DO TESTE DUCKSTATION")
    monitor_log(f"Intervalo: {CHECK_INTERVAL}s (5min)")
    monitor_log("=" * 60)

    last_fail_count = 0

    while True:
        try:
            # 1. Progresso do teste
            progress = get_test_progress()
            running, pid = is_duck_test_running()

            if progress:
                monitor_log(
                    f"Progresso: {progress['current']}/{progress['total']} "
                    f"({100*progress['current']/progress['total']:.1f}%) | "
                    f"OK={progress['ok']} FAIL={progress['fail']} UNK={progress['unk']} | "
                    f"Apagados={progress['deleted']} ({progress['gb_freed']}GB) | "
                    f"Proc={'OK' if running else 'MORTO'}"
                )
            else:
                monitor_log(f"Sem dados de progresso | Proc={'OK' if running else 'MORTO'}")

            # 2. Se processo morreu, reiniciar
            if not running:
                monitor_log("Processo do teste morreu! Reiniciando...")
                restart_duck_test()
                time.sleep(10)
                continue

            # 3. Verificar novas falhas
            fails = check_new_fails()
            if len(fails) > last_fail_count:
                new_fails = fails[last_fail_count:]
                monitor_log(f"NOVAS FALHAS: {len(new_fails)}")
                for path, detail in new_fails:
                    monitor_log(f"  FAIL: {Path(path).name} - {detail[:80]}")

                # Mover CHDs falhados para d:\romspsxduplicas
                moved = move_failed_to_dest(new_fails)
                if moved > 0:
                    monitor_log(f"  {moved} CHDs movidos para {DEST_DIR}")

                # Adicionar na fila do importre
                added = add_fails_to_importre(new_fails)
                if added > 0:
                    monitor_log(f"  {added} itens adicionados na fila do importre")

                last_fail_count = len(fails)

            # 4. Verificar se teste completou
            if progress and progress['current'] >= progress['total']:
                monitor_log("TESTE COMPLETO!")
                monitor_log(f"  OK={progress['ok']} FAIL={progress['fail']} UNK={progress['unk']}")
                monitor_log(f"  Apagados={progress['deleted']} arquivos ({progress['gb_freed']}GB)")
                # Nao sair - continuar monitorando por se reiniciar
                time.sleep(60)
                continue

        except Exception as e:
            monitor_log(f"ERRO no monitor: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
