"""
Monitor continuo - roda em loop e faz ajustes automaticos.
- Verifica progresso a cada 60s
- Re-enfileira falhas
- Reativa sites desativados indevidamente
- Trunca logs grandes
- Drena itens presos em in_progress
- Re-enfileira itens skipped
- Mostra estatisticas de throughput
"""
import json
import time
import os
import urllib.request
from pathlib import Path
from datetime import datetime

STATE = Path(r"D:\roms\library\roms\_importre_state")
QUEUE_PATH = STATE / "queue.json"
SITES_PATH = STATE / "sites.json"
LOG_PATH = STATE / "importre.log"
MONITOR_LOG = STATE / "monitor.log"

BANNED_SITES = {"blueroms", "cdromance", "vimm", "romspack", "freeroms", "myrient", "romsfun", "romhustler", "romsbase", "emuparadise"}

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [MONITOR] {msg}"
    print(line, flush=True)
    try:
        with open(MONITOR_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def get_status():
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=10)
        d = json.loads(r.read())
        return d.get("status", {})
    except:
        return None

def truncate_log():
    try:
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > 50 * 1024 * 1024:
            with open(LOG_PATH, "rb") as f:
                f.seek(-2 * 1024 * 1024, 2)
                data = f.read()
            with open(LOG_PATH, "wb") as f:
                f.write(data)
            log(f"Log truncado (mantidos ultimos 2MB)")
    except Exception as e:
        log(f"Erro ao truncar log: {e}")

def reenqueue_failed():
    try:
        with open(QUEUE_PATH, "r", encoding="utf-8") as f:
            q = json.load(f)
        failed = q.get("failed", {})
        if isinstance(failed, dict) and len(failed) > 0:
            queue = q.get("queue", [])
            for serial, info in list(failed.items()):
                queue.append({"serial": serial, "name": info.get("name", ""), "type": info.get("type", "commercial")})
            q["queue"] = queue
            q["failed"] = {}
            q["retry_count"] = {}
            with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                json.dump(q, f, indent=2, ensure_ascii=False)
            log(f"Re-enfileirados {len(failed)} itens falhados")
            return len(failed)
    except Exception as e:
        log(f"Erro ao re-enfileirar falhas: {e}")
    return 0

def reactivate_sites():
    try:
        with open(SITES_PATH, "r", encoding="utf-8") as f:
            sites = json.load(f)
        changed = False
        for k, v in sites.items():
            if k not in BANNED_SITES and not v.get("enabled") and v.get("fail_count", 0) < 999:
                v["enabled"] = True
                v["fail_count"] = 0
                changed = True
                log(f"Site {k} reativado")
        if changed:
            with open(SITES_PATH, "w", encoding="utf-8") as f:
                json.dump(sites, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Erro ao reativar sites: {e}")

def drain_stuck_in_progress(timeout_sec=600):
    try:
        with open(QUEUE_PATH, "r", encoding="utf-8") as f:
            q = json.load(f)
        in_prog = q.get("in_progress", {})
        now = time.time()
        drained = 0
        for serial, item in list(in_prog.items()):
            ts = item.get("timestamp", 0)
            if isinstance(ts, str):
                try:
                    from datetime import datetime as dt
                    ts = dt.fromisoformat(ts).timestamp()
                except:
                    ts = 0
            if ts and (now - ts) > timeout_sec:
                queue = q.get("queue", [])
                queue.append({"serial": serial, "name": item.get("name", ""), "type": item.get("type", "commercial")})
                q["queue"] = queue
                del in_prog[serial]
                drained += 1
        if drained > 0:
            q["in_progress"] = in_prog
            with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                json.dump(q, f, indent=2, ensure_ascii=False)
            log(f"Drenados {drained} itens presos em in_progress")
        return drained
    except Exception as e:
        log(f"Erro ao drenar in_progress: {e}")
        return 0

def check_skipped():
    """Se houver itens skipped, zerar o contador."""
    try:
        with open(QUEUE_PATH, "r", encoding="utf-8") as f:
            q = json.load(f)
        if q.get("skipped", 0) > 0:
            q["skipped"] = 0
            with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                json.dump(q, f, indent=2, ensure_ascii=False)
            log(f"Skipped zerado (era {q.get('skipped', 0)})")
    except Exception as e:
        log(f"Erro ao zerar skipped: {e}")

def main():
    log("=== MONITOR CONTINUO INICIADO ===")
    last_completed = 0
    last_time = time.time()
    cycle = 0

    while True:
        cycle += 1
        try:
            # 1. Truncar log
            truncate_log()

            # 2. Obter status
            status = get_status()
            if status:
                completed = status.get("completed", 0)
                pending = status.get("pending", 0)
                in_prog = status.get("in_progress", 0)
                failed = status.get("failed", 0)
                searching = status.get("searching", 0)
                downloading = status.get("downloading", 0)
                buffer_ready = status.get("buffer_ready", 0)

                # Calcular throughput
                now = time.time()
                elapsed = now - last_time
                delta_completed = completed - last_completed
                rate = delta_completed / (elapsed / 60) if elapsed > 0 else 0
                eta_min = pending / rate if rate > 0 else 999999

                log(f"Cycle {cycle}: pending={pending} in_prog={in_prog} search={searching} dl={downloading} ok={completed} fail={failed} buffer={buffer_ready} | rate={rate:.1f}/min ETA={eta_min:.0f}min")

                last_completed = completed
                last_time = now

                # 3. Se terminou tudo
                if pending == 0 and in_prog == 0:
                    log(f"=== TODOS OS DOWNLOADS COMPLETOS! {completed} itens ===")
                    break

                # 4. Re-enfileirar falhas
                if failed > 0:
                    reenqueue_failed()

                # 5. Drenar itens presos
                drain_stuck_in_progress()

                # 6. Reativar sites
                reactivate_sites()

                # 7. Zerar skipped
                check_skipped()

            else:
                log("API nao responde!")

        except Exception as e:
            log(f"ERRO: {e}")

        time.sleep(60)

if __name__ == "__main__":
    main()
