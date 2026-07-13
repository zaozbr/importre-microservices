import os
p = r"D:\roms\library\roms\_importre_state\importre.log"
sz = os.path.getsize(p)
print(f"size={sz/1024/1024:.1f}MB")
f = open(p, "r", encoding="utf-8", errors="replace")
f.seek(max(0, sz - 5000))
lines = f.read().split("\n")
for l in lines[-20:]:
    if l.strip():
        print(l[:150])
