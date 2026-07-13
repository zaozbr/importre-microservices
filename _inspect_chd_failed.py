"""Inspeciona arquivos em _chd_failed para diagnosticar problemas."""
from pathlib import Path
import re

failed_dir = Path(r"D:\roms\library\roms\psx\_chd_failed")
print(f"Arquivos em _chd_failed: {len(list(failed_dir.iterdir()))}")
for f in sorted(failed_dir.iterdir()):
    if not f.is_file():
        continue
    print(f"\n=== {f.name} ===")
    print(f"  tamanho: {f.stat().st_size}")
    if f.suffix == ".bin":
        sz = f.stat().st_size
        mod2352 = sz % 2352
        mod2048 = sz % 2048
        print(f"  mod 2352: {mod2352}, mod 2048: {mod2048}")
        with f.open("rb") as fh:
            head = fh.read(64)
        print(f"  head: {head.hex()[:64]}...")
        print(f"  zeros iniciais: {head[:16] == b'\\x00'*16}")
    elif f.suffix == ".cue":
        content = f.read_text(encoding="utf-8", errors="replace")
        print(f"  conteudo:\n{content[:500]}")
        refs = re.findall(r'FILE\s+"([^"]+)"', content)
        for ref in refs:
            ref_path = f.parent / ref
            exists = ref_path.exists()
            size = ref_path.stat().st_size if exists else 0
            print(f"  ref {ref}: exists={exists}, size={size}")
