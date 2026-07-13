"""Inspeciona os .bin que falharam na conversao."""
from pathlib import Path

psx = Path(r"D:\roms\library\roms\psx")
failed = [
    "DX-Jinsei-Game-III-SLPS-02469.bin",
    "King-of-Fighters-Kyo-SLPM-86095.bin",
    "Yeh-Yeh-Tennis-SLES-02272.bin",
    "Time-Gal-&-Ninja-Hayate-SLPS-00383.bin",
    "Tales-of-Eternia-[Disc1of3]-SLPS-03050.bin",
    "Aitakute…-Your-Smiles-In-My-Heart-[Disc1of4]-SLPM-86254.bin",
    "NOëL-La-Neige-(Disc-3)-SLPS-01195.bin",
    "NOëL-Not-Digital-(Disc-1)-SLPS-00304.bin",
]

for name in failed:
    f = psx / name
    print(f"=== {name} ===")
    if not f.exists():
        print("  nao existe em psx")
        continue
    sz = f.stat().st_size
    print(f"  tamanho: {sz}")
    print(f"  mod 2352: {sz % 2352}, mod 2048: {sz % 2048}")
    with f.open("rb") as fh:
        head = fh.read(64)
    print(f"  head: {head.hex()}")
    print(f"  zeros head: {head == b'\\x00'*64}")
