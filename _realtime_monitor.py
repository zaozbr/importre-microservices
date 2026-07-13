"""
Monitor em tempo real: mostra downloads ativos, velocidade, erros e estatisticas.
Atualiza a cada 3 segundos.
"""
import sys, os, time, json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STATE_DIR = r'D:\roms\library\roms\_importre_state'
QUEUE_PATH = os.path.join(STATE_DIR, 'queue.json')
DL_PROGRESS_PATH = os.path.join(STATE_DIR, 'dl_progress.json')
ERROR_LOG_PATH = os.path.join(STATE_DIR, 'download_errors.json')
LOG_PATH = os.path.join(STATE_DIR, 'emergency_download_log.json')


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def main():
    while True:
        clear_screen()
        print("=" * 70)
        print("  MONITOR EM TEMPO REAL — PSX ROM Downloader")
        print("=" * 70)

        # Queue status
        try:
            with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
                q = json.load(f)
            completed = q.get('completed', {})
            if not isinstance(completed, dict):
                completed = {}
            failed = q.get('failed', {})
            if not isinstance(failed, dict):
                failed = {}
            pending = q.get('queue', [])
            in_progress = q.get('in_progress', {})
            if not isinstance(in_progress, dict):
                in_progress = {}

            print(f"\n  Queue: {len(completed)} completos | {len(pending)} pendentes | {len(in_progress)} em progresso | {len(failed)} falhas")
        except Exception as e:
            print(f"\n  [ERRO] Queue: {e}")

        # Downloads ativos
        print(f"\n  --- DOWNLOADS ATIVOS ---")
        try:
            with open(DL_PROGRESS_PATH, 'r') as f:
                prog = json.load(f)
            now = time.time()
            active = []
            for serial, info in prog.items():
                ts = info.get('ts', 0)
                if now - ts < 30:  # ativo nos ultimos 30s
                    dl = info.get('downloaded', 0)
                    total = info.get('total', 0)
                    speed = info.get('speed', 0)
                    pct = 100 * dl / total if total > 0 else 0
                    eta = (total - dl) / speed if speed > 0 else 0
                    active.append((serial, dl, total, speed, pct, eta))

            if active:
                for serial, dl, total, speed, pct, eta in sorted(active, key=lambda x: -x[3]):
                    speed_mb = speed / 1024 / 1024
                    dl_mb = dl / 1024 / 1024
                    total_mb = total / 1024 / 1024
                    eta_str = f"{int(eta)}s" if eta < 60 else f"{int(eta/60)}m{int(eta%60)}s"
                    bar_len = 20
                    bar = '=' * int(pct / 100 * bar_len) + '-' * (bar_len - int(pct / 100 * bar_len))
                    print(f"  [{bar}] {serial}: {dl_mb:.1f}/{total_mb:.1f}MB ({pct:.0f}%) {speed_mb:.1f}MB/s ETA:{eta_str}")
            else:
                print(f"  (nenhum download ativo)")
        except:
            print(f"  (erro ao ler progresso)")

        # Erros recentes
        print(f"\n  --- ERROS RECENTES ---")
        try:
            with open(ERROR_LOG_PATH, 'r', encoding='utf-8') as f:
                errors = json.load(f)
            recent = sorted(errors.items(), key=lambda x: x[1].get('time', 0), reverse=True)[:5]
            if recent:
                for serial, info in recent:
                    err = info.get('error', '?')
                    mode = info.get('mode', '?')
                    ts = info.get('time_str', '?')
                    print(f"  [{ts}] {serial} ({mode}): {err}")
            else:
                print(f"  (nenhum erro)")
        except:
            print(f"  (sem log de erros)")

        # Log de downloads
        print(f"\n  --- LOG DE DOWNLOADS ---")
        try:
            with open(LOG_PATH, 'r', encoding='utf-8') as f:
                dl_log = json.load(f)
            ok = sum(1 for v in dl_log.values() if v.get('status', '').startswith('ok'))
            fail = sum(1 for v in dl_log.values() if 'failed' in v.get('status', '') or 'error' in v.get('status', ''))
            print(f"  Processados: {len(dl_log)} | OK: {ok} | Falhas: {fail}")
        except:
            print(f"  (sem log)")

        # Espaco em disco
        try:
            import shutil
            usage = shutil.disk_usage('D:\\')
            free_gb = usage.free / 1024 / 1024 / 1024
            total_gb = usage.total / 1024 / 1024 / 1024
            print(f"\n  Disco D: {free_gb:.1f}GB livres de {total_gb:.1f}GB")
        except:
            pass

        print(f"\n  Atualizado: {time.strftime('%H:%M:%S')}")
        print(f"  [Ctrl+C para sair]")

        time.sleep(3)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaindo...")
