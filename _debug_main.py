"""Roda importre main com captura de todos os erros."""
import sys, traceback
sys.path.insert(0, r"D:\roms\library\roms\psx")

try:
    print("1. Importando importre...", flush=True)
    import importre

    print("2. init_queue...", flush=True)
    importre.init_queue()

    print("3. load_presearch_buffer...", flush=True)
    importre.load_presearch_buffer()

    print("4. cleanup_stale_items...", flush=True)
    importre.cleanup_stale_items(max_age_seconds=60)

    print("5. clear_control...", flush=True)
    importre.clear_control()

    print("6. load_sites...", flush=True)
    sites = importre.load_sites()
    enabled = [k for k, v in sites.items() if v.get("enabled")]
    print(f"   {len(enabled)} sites ativos", flush=True)

    print("7. Testando queue_next_item...", flush=True)
    item = importre.queue_next_item(0)
    if item:
        print(f"   Item pego: {item.get('serial', '')} needs_search={item.get('_needs_search', '?')}", flush=True)
        # Devolver item
        importre.queue_return_item(item)
    else:
        print("   Nenhum item disponivel", flush=True)

    print("8. Testando buffer_load...", flush=True)
    buf = importre.buffer_load()
    print(f"   Buffer: {len(buf)} itens", flush=True)

    print("9. Testando get_presearched_url...", flush=True)
    if buf:
        first_serial = next(iter(buf.keys()))
        result = importre.get_presearched_url(first_serial)
        print(f"   get_presearched_url({first_serial}): {result}", flush=True)

    print("10. Testando downloader_process com timeout...", flush=True)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time as _time

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(importre.downloader_process, 0, 1, True)
        try:
            result = future.result(timeout=60)
            print(f"   Result: {result}", flush=True)
        except Exception as e:
            print(f"   Exception: {e}", flush=True)

    print("ALL OK!", flush=True)

except SystemExit as e:
    print(f"SYSTEM EXIT: code={e.code}", flush=True)
    traceback.print_exc()
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    traceback.print_exc()
