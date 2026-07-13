p = r'D:\roms\library\roms\psx\_chd_pipeline.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# The broken line has: raw.startswith(b\xfe\xff)  (missing quote before \xfe)
# Replace the entire if line
lines = c.split('\n')
for i, line in enumerate(lines):
    if 'raw.startswith' in line and '0xFF' not in line:
        lines[i] = "        if (len(raw) >= 2 and (raw[0] == 0xFF and raw[1] == 0xFE or raw[0] == 0xFE and raw[1] == 0xFF)):"
        print(f'Fixed line {i+1}')
        break

c = '\n'.join(lines)
with open(p, 'w', encoding='utf-8') as f:
    f.write(c)
print('DONE')
