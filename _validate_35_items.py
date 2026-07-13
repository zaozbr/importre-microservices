"""Valida os 35 itens do scan_roms antes de converter."""
import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _chd_convert_v2 import scan_roms
import re
from pathlib import Path

items = scan_roms()
print(f"Total de itens: {len(items)}")

problemas = []
for item in items:
    f = Path(item["file"])
    ext = item["ext"]
    print(f"\n{item['serial']:20s} {ext:6s} {f.name}")
    if not f.exists():
        print("  PROBLEMA: arquivo nao existe")
        problemas.append((f.name, "arquivo nao existe"))
        continue
    if ext == ".cue":
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            refs = re.findall(r'FILE\s+"([^"]+)"', content)
            missing = []
            for ref in refs:
                ref_path = f.parent / ref
                if not ref_path.exists():
                    missing.append(ref)
            if missing:
                print(f"  PROBLEMA: arquivos referenciados nao existem: {missing}")
                problemas.append((f.name, f"refs nao existem: {missing}"))
            else:
                print(f"  OK: {len(refs)} refs encontradas")
        except Exception as e:
            print(f"  PROBLEMA: erro lendo cue: {e}")
            problemas.append((f.name, f"erro cue: {e}"))
    elif ext == ".bin":
        sz = f.stat().st_size
        aligned = (sz % 2352 == 0) or (sz % 2048 == 0)
        print(f"  tamanho: {sz}, alinhado: {aligned}")
        if not aligned:
            problemas.append((f.name, f"bin nao alinhado: {sz}"))

print(f"\n\nTotal de problemas: {len(problemas)}")
for name, reason in problemas:
    print(f"  {name}: {reason}")
