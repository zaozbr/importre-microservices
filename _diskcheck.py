import os, time
d = r"D:\roms\library\roms\_importre_state\downloads"
t0 = time.time()
files = os.listdir(d)
total = sum(os.path.getsize(os.path.join(d, f)) for f in files if os.path.isfile(os.path.join(d, f)))
elapsed = time.time() - t0
print(f"files={len(files)} size={total/1024/1024/1024:.2f}GB time={elapsed:.1f}s")
# arquivos .aria2 = em download
aria2 = [f for f in files if f.endswith(".aria2")]
print(f"em_download={len(aria2)}")
