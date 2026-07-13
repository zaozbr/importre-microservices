import os
p = r"D:\roms\library\roms\_importre_state\importre.log"
sz = os.path.getsize(p)
print(f"size={sz/1024/1024:.1f}MB")
with open(p, "r", encoding="utf-8", errors="replace") as f:
    f.seek(max(0, sz - 8000))
    lines = f.read().split("\n")
for l in lines[-30:]:
    if l.strip():
        print(l[:150])
