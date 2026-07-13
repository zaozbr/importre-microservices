"""Limpa arquivos temporarios de teste do DX-Jinsei-Game-III e move .bin corrompido para falhas."""
from pathlib import Path
import shutil

psx = Path(r"D:\roms\library\roms\psx")
failed_dir = psx / "_chd_failed"
failed_dir.mkdir(exist_ok=True)

# Arquivos temporarios de teste
for name in [
    "DX-Jinsei-Game-III-SLPS-02469.cue",
    "DX-Jinsei-Game-III-SLPS-02469.test.chd",
]:
    f = psx / name
    if f.exists():
        f.unlink()
        print(f"Removido: {f}")

# Mover .bin corrompido para falhas
bin_file = psx / "DX-Jinsei-Game-III-SLPS-02469.bin"
if bin_file.exists():
    dst = failed_dir / bin_file.name
    if dst.exists():
        dst.unlink()
    shutil.move(str(bin_file), str(dst))
    print(f"Movido para falhas: {bin_file.name}")

print("Limpeza concluida.")
