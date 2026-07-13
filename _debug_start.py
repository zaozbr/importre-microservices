"""Debug: testa cada etapa da inicializacao do importre."""
import sys, traceback
sys.path.insert(0, r"D:\roms\library\roms\psx")

try:
    import importre
    print("1. import OK")
    importre.init_queue()
    print("2. init_queue OK")
    importre.load_presearch_buffer()
    print("3. load_presearch_buffer OK")
    importre.cleanup_stale_items(max_age_seconds=60)
    print("4. cleanup_stale_items OK")
    importre.clear_control()
    print("5. clear_control OK")
    sites = importre.load_sites()
    enabled = [k for k, v in sites.items() if v.get("enabled")]
    print(f"6. load_sites OK: {len(enabled)} ativos")
    print(f"7. Dashboard path: {importre.DASHBOARD_PATH}")
    print(f"8. QUEUE_PATH: {importre.QUEUE_PATH}")
    print(f"9. DEFAULT_WORKERS: {importre.DEFAULT_WORKERS}")
    print(f"10. SITE_MAX_PARALLEL archive_org: {importre.SITE_MAX_PARALLEL.get('archive_org')}")

    # Testar criacao de ThreadPoolExecutor e downloader
    print("11. Tentando iniciar 1 downloader...")
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(importre.downloader_process, 0, 1, True)
        result = future.result(timeout=30)
        print(f"12. Downloader result: {result}")

    print("ALL OK")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
