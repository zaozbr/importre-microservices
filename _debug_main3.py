"""Roda cada etapa de main() individualmente com prints."""
import sys, traceback
sys.path.insert(0, r"D:\roms\library\roms\psx")
import importre

try:
    print("A: init_queue", flush=True)
    importre.init_queue()
    print("B: load_presearch_buffer", flush=True)
    importre.load_presearch_buffer()
    print("C: cleanup_stale_items", flush=True)
    importre.cleanup_stale_items(max_age_seconds=60)
    print("D: clear_control", flush=True)
    importre.clear_control()
    print("E: load_sites", flush=True)
    sites = importre.load_sites()
    print(f"  {len([k for k,v in sites.items() if v.get('enabled')])} sites", flush=True)
    print("F: DASHBOARD_PATH exists?", flush=True)
    print(f"  {importre.DASHBOARD_PATH.exists()}", flush=True)
    print("G: Iniciando ThreadPoolExecutor com 4 downloaders", flush=True)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    print("H: ThreadPoolExecutor criado", flush=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        print("I: Submetendo 4 downloaders", flush=True)
        futures = [executor.submit(importre.downloader_process, w, 999, True) for w in range(4)]
        print("J: Submetidos. Esperando conclusao...", flush=True)
        for f in as_completed(futures):
            try:
                result = f.result()
                print(f"K: Downloader result: {result}", flush=True)
            except Exception as e:
                print(f"K: Downloader exception: {e}", flush=True)
                traceback.print_exc()
    print("L: ThreadPoolExecutor fechado", flush=True)
    print("ALL OK", flush=True)
except SystemExit as e:
    print(f"SYSTEM EXIT: code={e.code}", flush=True)
    traceback.print_exc()
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    traceback.print_exc()
