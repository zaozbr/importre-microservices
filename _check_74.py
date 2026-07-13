import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\roms\library\roms\psx')
from _chd_convert_v2 import scan_roms
from pathlib import Path

items = scan_roms()
print(f"Total: {len(items)}")

convertible = []
no_bin = []
for item in items:
    f = Path(item['file'])
    if item['ext'] == '.cue':
        content = f.read_text(encoding='utf-8', errors='replace')
        refs = re.findall(r'FILE\s+"([^"]+)"', content)
        has_bin = False
        for ref in refs:
            bin_path = f.parent / ref
            if bin_path.exists():
                has_bin = True
                break
        if has_bin:
            convertible.append(item)
        else:
            no_bin.append(item)
    elif item['ext'] in ('.bin', '.ecm'):
        if f.exists():
            convertible.append(item)
        else:
            no_bin.append(item)

print(f"Convertiveis (BIN existe): {len(convertible)}")
print(f"Sem BIN: {len(no_bin)}")
print()
print("Convertiveis:")
for item in convertible[:15]:
    print(f"  {item['ext']:>5} {Path(item['file']).name[:60]}")
print()
print("Sem BIN (primeiros 5):")
for item in no_bin[:5]:
    print(f"  {item['ext']:>5} {Path(item['file']).name[:60]}")
