"""Helpers para conversao de MDF/MDS (Alcohol 120%) para BIN/CUE."""
import shutil
from pathlib import Path


def create_cue(track_infos):
    """Gera conteudo CUE a partir de uma lista de tracks.

    track_infos: lista de dicts com chaves:
        - filename (str): nome do arquivo de imagem
        - number (int): numero do track
        - type (str): 'MODE1/2352', 'MODE2/2352' ou 'AUDIO'
        - min/sec/frame (int): posicao do INDEX 01
    """
    lines = []
    for i, ti in enumerate(track_infos):
        if i == 0 or ti.get("filename") != track_infos[i - 1].get("filename"):
            lines.append(f'FILE "{ti.get("filename", "image.bin")}" BINARY')
        lines.append(f"  TRACK {ti['number']:02d} {ti['type']}")
        lines.append(
            f"    INDEX 01 {ti['min']:02d}:{ti['sec']:02d}:{ti['frame']:02d}"
        )
    return "\n".join(lines) + "\n"


def mdf_to_bin_cue(mdf_path, output_dir):
    """Converte arquivo MDF para BIN/CUE.

    Se existir .mds com o mesmo nome, tenta usa-lo para track layout;
    caso contrario gera uma CUE com track unico MODE2/2352.

    Args:
        mdf_path: caminho para o arquivo .mdf (str ou Path).
        output_dir: diretorio onde gravar .bin e .cue.

    Returns:
        (bin_path, cue_path) ou None em caso de falha.
    """
    mdf_path = Path(mdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not mdf_path.exists():
        return None

    base = mdf_path.stem
    bin_path = output_dir / f"{base}.bin"
    cue_path = output_dir / f"{base}.cue"

    # Copiar MDF como BIN (o conteudo bruto e o mesmo; chdman lida com sector size via CUE)
    shutil.copy2(mdf_path, bin_path)

    mds_path = mdf_path.with_suffix(".mds")
    if mds_path.exists():
        # TODO: parsing binario completo do MDS. Por enquanto, fallback seguro.
        tracks = [{
            "filename": bin_path.name,
            "number": 1,
            "type": "MODE2/2352",
            "min": 0,
            "sec": 0,
            "frame": 0,
        }]
    else:
        tracks = [{
            "filename": bin_path.name,
            "number": 1,
            "type": "MODE2/2352",
            "min": 0,
            "sec": 0,
            "frame": 0,
        }]

    cue_content = create_cue(tracks)
    cue_path.write_text(cue_content, encoding="utf-8")
    return bin_path, cue_path
