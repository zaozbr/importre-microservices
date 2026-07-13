"""Converte descritor CloneCD (.ccd) para CUE sheet (.cue)."""
import configparser
from pathlib import Path


def ccd_to_cue(ccd_path, img_name=None):
    """Leia um arquivo .ccd e retorne o conteudo de um .cue equivalente.

    Args:
        ccd_path: caminho para o arquivo .ccd (str ou Path).
        img_name: nome do arquivo de imagem a referenciar no CUE. Se None,
                  usa o nome base do .ccd trocando a extensao para .img.

    Returns:
        str com o conteudo do CUE, ou None se nao houver tracks validas.
    """
    ccd_path = Path(ccd_path)
    if not ccd_path.exists():
        return None

    if img_name is None:
        for ext in (".img", ".bin", ".iso"):
            candidate = ccd_path.with_suffix(ext)
            if candidate.exists():
                img_name = candidate.name
                break
        if img_name is None:
            img_name = ccd_path.with_suffix(".img").name

    cfg = configparser.ConfigParser()
    cfg.read(ccd_path, encoding="utf-8")

    tracks = []
    for section in cfg.sections():
        if not section.startswith("Entry"):
            continue
        point_raw = cfg.get(section, "Point", fallback="")
        try:
            point = int(point_raw, 16) if point_raw.lower().startswith("0x") else int(point_raw)
        except ValueError:
            continue
        # Ignorar entradas de lead-in (A0, A1, A2, etc.)
        if point >= 0xA0:
            continue

        track_no = point
        control = cfg.get(section, "Control", fallback="0x04")
        try:
            control_val = int(control, 16) if control.lower().startswith("0x") else int(control)
        except ValueError:
            control_val = 0x04

        # Tipo de track: 0x04 = dados, 0x00 = audio
        is_data = bool(control_val & 0x04)

        track_section = f"TRACK {track_no}"
        mode = cfg.getint(track_section, "Mode", fallback=2) if cfg.has_section(track_section) else 2

        if is_data:
            if mode == 1:
                track_type = "MODE1/2352"
            else:
                track_type = "MODE2/2352"
        else:
            track_type = "AUDIO"

        # Offset relativo ao arquivo de imagem (frames)
        index1 = 0
        if cfg.has_section(track_section):
            index1 = cfg.getint(track_section, "INDEX 1", fallback=0)

        # Converter frames para MSF
        minutes = index1 // (75 * 60)
        seconds = (index1 // 75) % 60
        frames = index1 % 75

        tracks.append({
            "number": track_no,
            "type": track_type,
            "min": minutes,
            "sec": seconds,
            "frame": frames,
        })

    if not tracks:
        return None

    lines = [f'FILE "{img_name}" BINARY']
    for t in tracks:
        lines.append(f"  TRACK {t['number']:02d} {t['type']}")
        lines.append(f"    INDEX 01 {t['min']:02d}:{t['sec']:02d}:{t['frame']:02d}")

    return "\n".join(lines) + "\n"
