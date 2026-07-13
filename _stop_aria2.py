"""Para todos downloads ativos do aria2c."""
import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _aria2_manager import Aria2Manager
m = Aria2Manager()
active = m.tell_active()
print(f"Removendo {len(active)} download(s) ativo(s)...")
for d in active:
    m.remove(d["gid"])
    print(f"  Removido: {d['gid']}")
print("Concluído")
