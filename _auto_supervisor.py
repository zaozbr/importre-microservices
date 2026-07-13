"""
Supervisor autonomo resiliente para o importre.py.
- Monitora o processo a cada 30s
- Reinicia se morrer ou estagnar (>5min sem progresso)
- Mata instancias duplicadas
- Drena itens presos em in_progress (>10min)
- Reativa sites desativados indevidamente
- Trunca log se passar de 100MB
"""
import subprocess
import time
import json
import os
import signal
import sys
from pathlib import Path
from datetime import datetime

PSX_DIR = Path(r"D:\roms\library\roms\psx")
STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
LOG_PATH = STATE_DIR / "importre.log"
QUEUE_PATH = STATE_DIR / "queue.json"
SUPERVISOR_LOG = STATE_DIR / "supervisor.log"

WORKERS = 40
MAX_LOG_SIZE = 100 * 1024 * 1024  # 100MB
STAGNATION_TIMEOUT = 180  # 3 min sem progresso
IN_PROGRESS_TIMEOUT = 300  # 5 min preso em in_progress

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [SUPERVISOR] {msg}"
    print(line, flush=True)
    try:
        with open(SUPERVISOR_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def get_importre_pids():
    """Retorna PIDs de todos os processos importre (wrapper ou importre.py, nao server, nao supervisor)."""
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        pids = []
        for line in result.stdout.split("\n"):
            if ("_run_importre" in line or "importre.py" in line) and "importre_server" not in line and "importre_supervisor" not in line and "_auto_supervisor" not in line and "_continuous_monitor" not in line:
                parts = line.strip().split(",")
                if len(parts) >= 2:
                    try:
                        pid = int(parts[-1])
                        pids.append(pid)
                    except:
                        pass
        return pids
    except:
        return []

def get_server_pid():
    """Retorna PID do importre_server.py."""
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split("\n"):
            if "importre_server.py" in line:
                parts = line.strip().split(",")
                if len(parts) >= 2:
                    try:
                        return int(parts[-1])
                    except:
                        pass
        return None
    except:
        return None

def kill_pid(pid):
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=10)
        log(f"Processo {pid} morto")
    except:
        pass

def start_importre():
    """Inicia o wrapper _run_importre.py em background (nao usa importre.py main() — tem bug de crash)."""
    log("Iniciando _run_importre.py (wrapper)...")
    try:
        subprocess.Popen(
            ["python", "-u", "_run_importre.py"],
            cwd=str(PSX_DIR),
            stdout=open(STATE_DIR / "importre_out.log", "w"),
            stderr=open(STATE_DIR / "importre_err.log", "w"),
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        time.sleep(8)
        pids = get_importre_pids()
        if pids:
            log(f"wrapper iniciado: PIDs={pids}")
            return True
        else:
            err_path = STATE_DIR / "importre_err.log"
            if err_path.exists() and err_path.stat().st_size > 0:
                err = err_path.read_text(encoding="utf-8", errors="replace")[:500]
                log(f"ERRO: wrapper nao iniciou! stderr: {err}")
            else:
                log("ERRO: wrapper nao iniciou! Sem stderr.")
            return False
    except Exception as e:
        log(f"ERRO ao iniciar wrapper: {e}")
        return False

def start_server():
    """Inicia importre_server.py em background."""
    log("Iniciando importre_server.py...")
    try:
        subprocess.Popen(
            ["python", "importre_server.py", "8765"],
            cwd=str(PSX_DIR),
            stdout=open(STATE_DIR / "server.log", "w"),
            stderr=open(STATE_DIR / "server_err.log", "w"),
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        time.sleep(3)
        log("importre_server.py iniciado")
        return True
    except Exception as e:
        log(f"ERRO ao iniciar server: {e}")
        return False

def truncate_log():
    """Trunca o log se passar de MAX_LOG_SIZE."""
    try:
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > MAX_LOG_SIZE:
            # Manter ultimos 5MB
            with open(LOG_PATH, "rb") as f:
                f.seek(-5 * 1024 * 1024, 2)
                data = f.read()
            with open(LOG_PATH, "wb") as f:
                f.write(data)
            log(f"Log truncado (era >{MAX_LOG_SIZE//1024//1024}MB, mantidos ultimos 5MB)")
    except Exception as e:
        log(f"Erro ao truncar log: {e}")

def get_status():
    """Obtem status via API."""
    try:
        import urllib.request
        r = urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=10)
        d = json.loads(r.read())
        return d.get("status", {})
    except:
        return None

def drain_stuck_in_progress(q_data):
    """Drena itens presos em in_progress ha mais de IN_PROGRESS_TIMEOUT segundos."""
    in_prog = q_data.get("in_progress", {})
    now = time.time()
    drained = []
    for serial, item in list(in_prog.items()):
        ts = item.get("timestamp", 0)
        if isinstance(ts, str):
            try:
                from datetime import datetime
                ts = datetime.fromisoformat(ts).timestamp()
            except:
                ts = 0
        if ts and (now - ts) > IN_PROGRESS_TIMEOUT:
            drained.append(serial)
            # Voltar para a fila
            queue = q_data.get("queue", [])
            queue.append({"serial": serial, "name": item.get("name", ""), "type": item.get("type", "commercial")})
            q_data["queue"] = queue
            del in_prog[serial]
    if drained:
        q_data["in_progress"] = in_prog
        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
            json.dump(q_data, f, indent=2, ensure_ascii=False)
        log(f"Drenados {len(drained)} itens presos: {drained[:5]}...")
    return len(drained)

def check_sites():
    """Reativa sites que foram desativados indevidamente (fail_count alto mas nao banidos)."""
    sites_path = STATE_DIR / "sites.json"
    BANNED = {"blueroms", "cdromance", "vimm", "romspack", "freeroms", "myrient", "romsfun", "romhustler", "romsbase", "emuparadise"}
    try:
        with open(sites_path, "r", encoding="utf-8") as f:
            sites = json.load(f)
        changed = False
        for k, v in sites.items():
            if k not in BANNED and not v.get("enabled") and v.get("fail_count", 0) < 999:
                v["enabled"] = True
                v["fail_count"] = 0
                changed = True
                log(f"Site {k} reativado (fail_count resetado)")
        if changed:
            with open(sites_path, "w", encoding="utf-8") as f:
                json.dump(sites, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Erro ao verificar sites: {e}")

def main():
    log("=== SUPERVISOR RESILIENTE INICIADO ===")
    log(f"Workers: {WORKERS}, Stagnation: {STAGNATION_TIMEOUT}s, InProgress: {IN_PROGRESS_TIMEOUT}s")

    restart_count = 0
    last_progress = {"completed": 0, "pending": 0, "time": time.time()}
    consecutive_failures = 0

    while True:
        try:
            # 1. Truncar log — DESATIVADO (causa conflito com wrapper)
            # truncate_log()

            # 2. Verificar processos
            pids = get_importre_pids()
            server_pid = get_server_pid()
            log(f"DEBUG: pids={pids} server_pid={server_pid}")

            # 3. Garantir server rodando (servidor separado, nao importre.py)
            if not server_pid:
                log("Server nao rodando! Iniciando...")
                start_server()
                time.sleep(3)
                server_pid = get_server_pid()

            # 4. Obter status
            log("DEBUG: obtendo status...")
            status = get_status()
            log(f"DEBUG: status={status is not None}")

            if status:
                completed = status.get("completed", 0)
                pending = status.get("pending", 0)
                in_prog = status.get("in_progress", 0)
                failed = status.get("failed", 0)
                searching = status.get("searching", 0)
                downloading = status.get("downloading", 0)

                log(f"Status: pending={pending} in_prog={in_prog} search={searching} dl={downloading} ok={completed} fail={failed} | PIDs={pids}")

                # 5. Verificar estagnacao
                now = time.time()
                if completed > last_progress["completed"] or pending != last_progress["pending"]:
                    last_progress = {"completed": completed, "pending": pending, "time": now}
                    consecutive_failures = 0
                else:
                    stagnant_time = now - last_progress["time"]
                    if stagnant_time > STAGNATION_TIMEOUT and pending > 0:
                        log(f"ESTAGNACAO detectada ({stagnant_time:.0f}s sem progresso)! Reiniciando...")
                        for pid in pids:
                            kill_pid(pid)
                        time.sleep(3)
                        start_importre()
                        restart_count += 1
                        consecutive_failures += 1
                        last_progress = {"completed": completed, "pending": pending, "time": now}
                        if consecutive_failures >= 5:
                            log("5 falhas consecutivas! Esperando 60s...")
                            time.sleep(60)
                            consecutive_failures = 0

                # 6. Drenar in_progress preso — DESATIVADO (causa deadlock com file_lock)
                # O proprio _clean_restart.py faz isso quando o processo reinicia

                # 7. Se nao ha processos importre rodando, iniciar
                if not pids and pending > 0:
                    # Dupla verificacao — evitar iniciar duplicata
                    time.sleep(2)
                    pids = get_importre_pids()
                    if pids:
                        log(f"Wrapper ja rodando (detectado na 2a verificacao): PIDs={pids}")
                    else:
                        log("Nenhum importre.py rodando! Iniciando...")
                        start_importre()
                        restart_count += 1

                # 8. Se pending=0 e in_progress=0, terminou!
                if pending == 0 and in_prog == 0:
                    log("=== TODOS OS DOWNLOADS COMPLETOS! ===")
                    log(f"Total completado: {completed}")
                    break

            else:
                log("API nao responde! Verificando processos...")
                if not pids:
                    log("Nenhum processo rodando. Iniciando...")
                    if not server_pid:
                        start_server()
                        time.sleep(3)
                    start_importre()
                    restart_count += 1

            # 9. Reativar sites — DESATIVADO (causa conflito com wrapper)
            # check_sites()

            log(f"Reinicios: {restart_count} | Falhas consec: {consecutive_failures}")

        except Exception as e:
            log(f"ERRO no loop principal: {e}")

        time.sleep(30)

if __name__ == "__main__":
    main()
