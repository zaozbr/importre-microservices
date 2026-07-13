"""Verifica velocidade atual do aria2c."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _aria2_manager

mgr = _aria2_manager.Aria2Manager(port=6801, secret="psx_download_2026")
if not mgr.is_daemon_running():
    print("aria2c nao rodando!")
    sys.exit(1)

for i in range(6):
    try:
        stat = mgr.get_global_stat()
        speed = int(stat.get("downloadSpeed", 0))
        speed_mb = speed / 1024 / 1024
        active = stat.get("numActive")
        stopped = stat.get("numStopped")
        waiting = stat.get("numWaiting")
        
        # Contar completos
        completed = 0
        if int(stopped) > 0:
            try:
                stopped_list = mgr.tell_stopped(0, 200)
                completed = sum(1 for d in stopped_list if d.get("status") == "complete")
            except:
                pass
        
        marker = "OK" if speed_mb >= 20 else ("WARN" if speed_mb >= 5 else "LOW")
        print(f"[{i*10:3d}s] {marker} {speed_mb:6.2f}MB/s active={active} waiting={waiting} stopped={stopped} completed={completed}")
    except Exception as e:
        print(f"[{i*10}s] erro: {str(e)[:60]}")
    time.sleep(10)
