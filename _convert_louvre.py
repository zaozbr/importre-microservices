#!/usr/bin/env python3
"""Converte .img (CloneCD) para .chd gerando CUE temporario."""
import subprocess, sys, re, shutil
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PSX = Path(r"D:\roms\library\roms\psx")
CHDMAN = PSX / "chdman.exe"
F_TEMP = Path(r"F:\chd_temp")
F_TEMP.mkdir(exist_ok=True)

discs = [
    "Louvre - The Final Curse (Europe) (Disc 1)",
    "Louvre - The Final Curse (Europe) (Disc 2)",
]

for disc in discs:
    img = PSX / disc / f"{disc}.img"
    if not img.exists():
        print(f"NAO ENCONTRADO: {img}")
        continue

    # Verificar se CHD ja existe
    chd_name = disc.replace(" - ", "-").replace(" ", "-").replace(",", "") + ".chd"
    chd_name = re.sub(r"[^\w\s-]", "", chd_name)
    chd_name = re.sub(r"\s+", "-", chd_name) + ".chd"
    chd_dst = PSX / chd_name
    if chd_dst.exists() and chd_dst.stat().st_size > 1024 * 1024:
        print(f"JA EXISTE: {chd_dst.name} ({chd_dst.stat().st_size//1024}KB)")
        continue

    # Gerar CUE temporario
    cue_tmp = F_TEMP / f"_louvre_{disc[-7:]}.cue"
    cue_tmp.write_text(f'FILE "{img.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n', encoding="utf-8")

    # Copiar IMG para F: (SSD rapido)
    img_tmp = F_TEMP / img.name
    if not img_tmp.exists():
        print(f"Copiando {img.name} para F:...")
        shutil.copy2(str(img), str(img_tmp))

    # CUE temporario apontando para img em F:
    cue_f = F_TEMP / f"_louvre_{disc[-7:]}.cue"
    cue_f.write_text(f'FILE "{img_tmp.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n', encoding="utf-8")

    chd_out = F_TEMP / chd_name
    print(f"Convertendo {disc} -> {chd_name}...")

    result = subprocess.run(
        [str(CHDMAN), "createcd", "-i", str(cue_f), "-o", str(chd_out), "-f"],
        capture_output=True, text=True, timeout=600
    )

    if chd_out.exists() and chd_out.stat().st_size > 1024 * 1024:
        # Verify
        verify = subprocess.run(
            [str(CHDMAN), "verify", "-i", str(chd_out)],
            capture_output=True, text=True, timeout=120
        )
        if verify.returncode == 0:
            # Mover CHD para psx/
            shutil.move(str(chd_out), str(chd_dst))
            print(f"OK: {chd_dst.name} ({chd_dst.stat().st_size//1024}KB)")
        else:
            print(f"VERIFY FALHOU: {verify.stderr[:200]}")
            chd_out.unlink(missing_ok=True)
    else:
        print(f"FALHA: {result.stderr[:200]}")

    # Limpar temp
    cue_f.unlink(missing_ok=True)
    img_tmp.unlink(missing_ok=True)

print("Concluido")
