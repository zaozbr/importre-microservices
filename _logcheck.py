import os
p = r"D:\roms\library\roms\_importre_state\aria2c.log"
sz = os.path.getsize(p)
print(f"Log size: {sz} bytes")
if sz > 0:
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    lines = content.split("\n")
    print(f"Total lines: {len(lines)}")
    # Mostrar últimas 30 linhas
    for l in lines[-30:]:
        if l.strip():
            print(l[:150])
else:
    print("Log vazio — sem erros!")
