"""Verifica .cue que referenciam arquivos inexistentes."""
from pathlib import Path
import re

PSX_DIR = Path(r"D:\roms\library\roms\psx")

broken = []
for cue in PSX_DIR.glob("*.cue"):
    content = cue.read_text(encoding="utf-8", errors="replace")
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    if not refs:
        continue
    ok = True
    missing_refs = []
    for ref in refs:
        if not (cue.parent / ref).exists():
            ok = False
            missing_refs.append(ref)
    if not ok:
        broken.append((cue.name, missing_refs))

out_path = PSX_DIR / "_broken_cues_report.txt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"CUEs quebrados: {len(broken)}\n")
    for cue_name, refs in broken:
        f.write(f"\n{cue_name}\n")
        for ref in refs:
            f.write(f"  [FALTANDO] {ref}\n")

print(f"CUEs quebrados: {len(broken)}")
print(f"Relatorio salvo em: {out_path}")
