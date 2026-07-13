"""
Wrapper para rodar importre sem o bug de crash do main().
Nao usa importre.log.info() — causa crash no Python 3.14.
"""
import sys, os, time, traceback, socket
sys.path.insert(0, r"D:\roms\library\roms\psx")
os.chdir(r"D:\roms\library\roms\psx")

# Corrigir encoding para evitar UnicodeEncodeError com caracteres japoneses
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Timeout global de socket — Tor e mais lento, dar mais tempo
socket.setdefaulttimeout(120)

# archive.org agora acessivel diretamente (sem proxy)
# Tor mantido como fallback apenas em archive_request() dentro do importre.py
# NAO usar proxy global — downloads diretos sao muito mais rapidos
# Remover qualquer proxy residual do ambiente
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('NO_PROXY', None)

import importre
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Configurar logging manualmente (nao usar importre.log)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(r"D:\roms\library\roms\_importre_state\importre.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("wrapper")

def main():
    print("[WRAPPER] Iniciando...", flush=True)

    # Inicializar
    importre.init_queue()
    print("[WRAPPER] init_queue done", flush=True)
    importre.load_presearch_buffer()
    print("[WRAPPER] load_presearch_buffer done", flush=True)

    # Limpar itens presos
    try:
        importre.cleanup_stale_items(max_age_seconds=60)
    except Exception as e:
        print(f"[WRAPPER] cleanup error (ignored): {e}", flush=True)
    print("[WRAPPER] cleanup done", flush=True)

    importre.clear_control()
    print("[WRAPPER] clear_control done", flush=True)

    # Configurar workers — 5 workers para nao sobrecarregar Tor
    NUM_WORKERS = 5
    NUM_ROUNDS = 999
    LIMIT = 999

    print(f"[WRAPPER] Iniciando {NUM_WORKERS} downloaders", flush=True)

    for round_num in range(1, NUM_ROUNDS + 1):
        action, _ = importre.check_control()
        if action == "stop":
            print("[WRAPPER] Stop recebido", flush=True)
            break

        print(f"[WRAPPER] === RODADA {round_num} ===", flush=True)

        try:
            executor = ThreadPoolExecutor(max_workers=NUM_WORKERS)
            futures = [executor.submit(importre.downloader_process, w, LIMIT, True) for w in range(NUM_WORKERS)]
            print(f"[WRAPPER] {NUM_WORKERS} downloaders submetidos", flush=True)
            # Timeout de 10 min por rodada — Tor pode ser mais lento
            try:
                for f in as_completed(futures, timeout=600):
                    try:
                        result = f.result()
                        print(f"[WRAPPER] Downloader: {result} itens", flush=True)
                    except Exception as e:
                        print(f"[WRAPPER] Downloader erro: {e}", flush=True)
            except TimeoutError:
                print("[WRAPPER] Timeout 5min — cancelando downloads travados", flush=True)
                for f in futures:
                    f.cancel()
            # NAO usar with — shutdown(wait=False) para nao bloquear
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            print(f"[WRAPPER] ThreadPool erro: {e}", flush=True)
            traceback.print_exc()
        except Exception as e:
            print(f"[WRAPPER] ThreadPool erro: {e}", flush=True)
            traceback.print_exc()

        # Verificar status
        status = importre.queue_get_status()
        pending = status.get("pending", 0)
        in_prog = status.get("in_progress", 0)
        completed = status.get("completed", 0)
        print(f"[WRAPPER] Status: pending={pending} in_prog={in_prog} completed={completed}", flush=True)

        if pending == 0 and in_prog == 0:
            print(f"[WRAPPER] === TODOS COMPLETOS! {completed} itens ===", flush=True)
            break

        time.sleep(1)

    print("[WRAPPER] Encerrando", flush=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[WRAPPER] Interrompido", flush=True)
    except Exception as e:
        print(f"[WRAPPER] ERRO FATAL: {e}", flush=True)
        traceback.print_exc()
