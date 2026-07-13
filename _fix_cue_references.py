"""Corrige referencias de .cue para .bin quando os nomes nao batem exatamente."""
from pathlib import Path
import re

PSX_DIR = Path(r"D:\roms\library\roms\psx")

def normalize_name(name):
    """Normaliza nome para comparacao: minusculo, remove conteudo entre colchetes/parenteses especificos, track numbers."""
    n = name.lower()
    # Remove serial entre colchetes como [SLPS-00407]
    n = re.sub(r"\[\s*[a-z]+-\d+\s*\]", "", n, flags=re.I)
    # Remove (J) / (Japan) / (Europe) / (USA) etc. — pais padrao
    n = re.sub(r"\(\s*(j|e|u|japan|europe|usa|germany|france|spain|italy)\s*\)", "", n, flags=re.I)
    # Normaliza track numbers: (Track 01) -> (track 1)
    n = re.sub(r"\(track 0+(\d+)\)", r"(track \1)", n, flags=re.I)
    # Remove v1.1, v1.02 etc.
    n = re.sub(r"\(\s*v?\d+\.\d+\s*\)", "", n, flags=re.I)
    # Remove espacos extras e caracteres nao alfanumericos
    n = re.sub(r"[^\w\s]", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n

def find_bin_match(cue_dir, ref_name, all_bins):
    """Tenta achar arquivo .bin correspondente ao nome referenciado."""
    ref_path = cue_dir / ref_name
    if ref_path.exists():
        return ref_path.name

    ref_norm = normalize_name(Path(ref_name).stem)
    ref_track = re.search(r"track\s+(\d+)", ref_name.lower())

    candidates = []
    for f in all_bins:
        f_norm = normalize_name(f.stem)
        # Match exato normalizado
        if ref_norm == f_norm:
            return f.name
        # Se ref tem track, f tambem deve ter o mesmo track
        if ref_track:
            f_track = re.search(r"track\s+(\d+)", f.stem.lower())
            if f_track and ref_track.group(1) == f_track.group(1):
                # Compara base sem track
                ref_base = re.sub(r"\(track\s+\d+\)", "", ref_name.lower()).strip()
                f_base = re.sub(r"\(track\s+\d+\)", "", f.stem.lower()).strip()
                ref_base = re.sub(r"[^\w\s]", "", ref_base)
                f_base = re.sub(r"[^\w\s]", "", f_base)
                if ref_base == f_base or ref_base in f_base or f_base in ref_base:
                    candidates.append(f)
        else:
            # Sem track: substring match
            if ref_norm in f_norm or f_norm in ref_norm:
                candidates.append(f)

    # Se houver apenas um candidato, usar
    if len(candidates) == 1:
        return candidates[0].name

    return None

fixed_count = 0
for cue in PSX_DIR.glob("*.cue"):
    all_bins = list(cue.parent.glob("*.bin"))
    content = cue.read_text(encoding="utf-8", errors="replace")
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    if not refs:
        continue

    new_content = content
    changed = False
    for ref in refs:
        if (cue.parent / ref).exists():
            continue
        match = find_bin_match(cue.parent, ref, all_bins)
        if match:
            new_content = new_content.replace(f'"{ref}"', f'"{match}"')
            changed = True
            print(f"  {cue.name}: '{ref}' -> '{match}'")
        else:
            print(f"  [SEM MATCH] {cue.name}: '{ref}'")

    if changed:
        cue.write_text(new_content, encoding="utf-8")
        fixed_count += 1

print(f"\nCUEs corrigidos: {fixed_count}")
