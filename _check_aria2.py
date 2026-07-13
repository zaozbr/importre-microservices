"""Verifica se o daemon aria2c está rodando."""
import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _aria2_manager import Aria2Manager
m = Aria2Manager()
print(f"Daemon rodando: {m.is_daemon_running()}")
if m.is_daemon_running():
    s = m.get_summary()
    print(f"Active: {s.get('active', 0)}")
    print(f"Speed: {s.get('download_speed', 0) / 1e6:.1f} MB/s")
