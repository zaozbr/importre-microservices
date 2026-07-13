import os
p = r'D:\roms\library\roms\psx\_chd_pipeline.py'
with open(p, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed = False
with open(p, 'w', encoding='utf-8') as f:
    for i, line in enumerate(lines):
        if 'raw.startswith' in line and '0xFF' not in line and 'len(raw)' not in line:
            f.write("        if (len(raw) >= 2 and (raw[0] == 0xFF and raw[1] == 0xFE or raw[0] == 0xFE and raw[1] == 0xFF)):\n")
            fixed = True
            print(f"Fixed line {i+1}: {line.rstrip()}")
        else:
            f.write(line)

if fixed:
    print("File saved successfully")
else:
    print("No line needed fixing")

# Verify
with open(p, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i+1 == 319:
            print(f"Line 319 now: {line.rstrip()}")
            break
