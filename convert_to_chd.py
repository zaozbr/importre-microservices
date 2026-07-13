"""
convert_to_chd.py — Converte ROMs em formato antigo (.bin, .img, .iso, .ecm) para .chd
Usa chdman.exe (MAME Compressed Hunks of Data).

Estrategia:
1. Encontra todos os .bin/.img/.iso/.ecm no diretorio PSX
2. Para cada arquivo, converte para .chd com chdman createcd
3. Se conversao OK, deleta o arquivo original
4. Para .ecm, primeiro descomprime para .bin com unecm
5. Para .bin com .cue, usa o .cue como input (chdman precisa do cue)

Uso:
    python convert_to_chd.py --dry-run     # apenas lista o que seria convertido
    python convert_to_chd.py --limit 10    # converte apenas 10 arquivos
    python convert_to_chd.py               # converte tudo
    python convert_to_chd.py --worker 4    # converte com 4 workers paralelos
"""
import os
import sys
import re
import time
import json
import argparse
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
CHDMAN = SCRIPT_DIR / "chdman.exe"
PSX_DIR = SCRIPT_DIR
STATE_DIR = Path(r"D:\roms\library\roms\_importre_state")
CONVERT_LOG = STATE_DIR / "convert_log.json"
CONVERT_STATE = STATE_DIR / "convert_state.json"

OLD_EXTS = {".bin", ".img", ".iso"}
SPECIAL_EXTS = {".ecm"}
CUE_EXT = ".cue"
CHD_EXT = ".chd"

# Arquivos .bin que sao multi-track (tem .cue) precisam do cue
# Arquivos .bin sem .cue sao single-track e podem ser convertidos diretamente

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def find_roms_to_convert():
    """Encontra todos os arquivos .bin/.img/.iso/.ecm que ainda nao tem .chd correspondente."""
    roms = []
    for f in sorted(PSX_DIR.iterdir()):
        ext = f.suffix.lower()
        if ext not in OLD_EXTS and ext not in SPECIAL_EXTS:
            continue
        # Pular se ja existe .chd correspondente
        # Nome do .chd seria: {stem}.chd ou {stem}_disc1.chd etc
        stem = f.stem
        chd_name = f"{stem}.chd"
        chd_path = PSX_DIR / chd_name
        if chd_path.exists():
            continue  # ja tem CHD
        # Para .bin, verificar se tem .cue
        cue_path = PSX_DIR / f"{stem}.cue"
        has_cue = cue_path.exists()
        # Verificar se nao e um .bin de track secundario (ex: "Game (Track 2).bin")
        # Esses sao convertidos junto com o .bin principal via .cue
        if ext == ".bin" and ("track" in f.stem.lower() or "(track" in f.stem.lower()):
            # Pular tracks secundarios — serao convertidos via .cue do track 1
            continue
        size = f.stat().st_size
        roms.append({
            "path": f,
            "name": f.name,
            "stem": stem,
            "ext": ext,
            "size": size,
            "has_cue": has_cue,
            "cue_path": cue_path if has_cue else None,
        })
    return roms

def convert_bin_to_chd(rom_info, dry_run=False):
    """Converte um arquivo .bin/.img/.iso para .chd usando chdman."""
    src = rom_info["path"]
    stem = rom_info["stem"]
    chd_path = PSX_DIR / f"{stem}.chd"
    
    if dry_run:
        return True, f"[dry-run] converteria {src.name} -> {chd_path.name}"
    
    try:
        # Para .bin com .cue, usar o .cue como input
        if rom_info["has_cue"]:
            input_file = rom_info["cue_path"]
        else:
            input_file = src
        
        # chdman createcd -i input -o output.chd
        cmd = [str(CHDMAN), "createcd", "-i", str(input_file), "-o", str(chd_path), "-f"]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        
        if result.returncode != 0:
            # Limpar .chd parcial
            if chd_path.exists():
                chd_path.unlink(missing_ok=True)
            return False, f"chdman falhou: {result.stderr[:200]}"
        
        # Verificar se o .chd foi criado e tem tamanho razoavel
        if not chd_path.exists() or chd_path.stat().st_size < 1024 * 1024:
            if chd_path.exists():
                chd_path.unlink(missing_ok=True)
            return False, "CHD muito pequeno ou nao criado"
        
        chd_size = chd_path.stat().st_size
        original_size = src.stat().st_size
        ratio = chd_size / original_size if original_size > 0 else 0
        
        # Deletar arquivo original + arquivos relacionados (.cue, tracks secundarios)
        deleted = []
        src.unlink(missing_ok=True)
        deleted.append(src.name)
        
        # Deletar .cue
        if rom_info["has_cue"]:
            rom_info["cue_path"].unlink(missing_ok=True)
            deleted.append(rom_info["cue_path"].name)
        
        # Deletar tracks secundarios (se for .bin principal com .cue)
        if rom_info["has_cue"]:
            for f in PSX_DIR.iterdir():
                if f.stem.startswith(stem) and f.suffix.lower() == ".bin" and f != src:
                    f.unlink(missing_ok=True)
                    deleted.append(f.name)
        
        return True, f"OK: {chd_path.name} ({chd_size//1024//1024}MB, ratio={ratio:.2f}, deletados: {deleted})"
    
    except subprocess.TimeoutExpired:
        if chd_path.exists():
            chd_path.unlink(missing_ok=True)
        return False, f"timeout na conversao de {src.name}"
    except Exception as e:
        if chd_path.exists():
            chd_path.unlink(missing_ok=True)
        return False, f"erro: {str(e)[:200]}"

def convert_ecm_to_chd(rom_info, dry_run=False):
    """Converte .ecm para .chd (primeiro descomprime para .bin, depois converte)."""
    src = rom_info["path"]
    stem = rom_info["stem"]
    bin_path = PSX_DIR / f"{stem}.bin"
    chd_path = PSX_DIR / f"{stem}.chd"
    
    if dry_run:
        return True, f"[dry-run] converteria {src.name} -> {chd_path.name}"
    
    try:
        # Descomprimir .ecm para .bin
        # ECM nao tem ferramenta padrao — usar ecmtool ou unecm
        # Tentar com python puro: ECM e um formato simples
        # Na pratica, vamos pular .ecm por enquanto (poucos arquivos)
        return False, "conversao .ecm nao suportada (use unecm manualmente)"
    except Exception as e:
        return False, f"erro: {str(e)[:200]}"

def save_convert_state(state):
    try:
        CONVERT_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass

def load_convert_state():
    try:
        if CONVERT_STATE.exists():
            return json.loads(CONVERT_STATE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"converted": [], "failed": [], "total_saved": 0}

def main():
    parser = argparse.ArgumentParser(description="Converte ROMs antigos para .chd")
    parser.add_argument("--dry-run", action="store_true", help="Apenas lista, nao converte")
    parser.add_argument("--limit", type=int, help="Limite de arquivos a converter")
    parser.add_argument("--workers", type=int, default=1, help="Workers paralelos (cuidado: CPU intensivo)")
    parser.add_argument("--min-size", type=int, default=10, help="Tamanho minimo em MB (pular arquivos pequenos)")
    args = parser.parse_args()
    
    if not CHDMAN.exists():
        print(f"ERRO: chdman.exe nao encontrado em {CHDMAN}")
        sys.exit(1)
    
    log("Procurando ROMs em formato antigo...")
    roms = find_roms_to_convert()
    
    # Filtrar por tamanho minimo
    min_bytes = args.min_size * 1024 * 1024
    roms = [r for r in roms if r["size"] >= min_bytes]
    
    # Filtrar .ecm (nao suportado ainda)
    ecm_roms = [r for r in roms if r["ext"] == ".ecm"]
    bin_roms = [r for r in roms if r["ext"] != ".ecm"]
    
    log(f"Encontrados: {len(bin_roms)} .bin/.img/.iso + {len(ecm_roms)} .ecm")
    
    total_size = sum(r["size"] for r in bin_roms)
    log(f"Tamanho total a converter: {total_size//1024//1024//1024}GB")
    
    if args.limit:
        bin_roms = bin_roms[:args.limit]
        log(f"Limitando a {len(bin_roms)} arquivos")
    
    if args.dry_run:
        log("=== DRY RUN ===")
        for r in bin_roms[:20]:
            log(f"  {r['name']:60} {r['size']//1024//1024}MB cue={r['has_cue']}")
        if len(bin_roms) > 20:
            log(f"  ... e mais {len(bin_roms)-20}")
        return
    
    state = load_convert_state()
    log(f"Estado anterior: {len(state['converted'])} convertidos, {len(state['failed'])} falhas")
    
    # Converter
    success_count = 0
    fail_count = 0
    saved_bytes = 0
    t0 = time.time()
    
    if args.workers > 1:
        # Conversao paralela (cuidado: CPU intensivo)
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(convert_bin_to_chd, r): r for r in bin_roms}
            for future in as_completed(futures):
                rom = futures[future]
                try:
                    ok, msg = future.result()
                    if ok:
                        success_count += 1
                        # Estimar economia (CHD ~50% do tamanho original)
                        saved = rom["size"] // 2
                        saved_bytes += saved
                        log(f"[{success_count}/{len(bin_roms)}] OK: {msg}")
                    else:
                        fail_count += 1
                        log(f"[FAIL] {rom['name']}: {msg}")
                except Exception as e:
                    fail_count += 1
                    log(f"[FAIL] {rom['name']}: {e}")
    else:
        # Conversao sequencial (mais seguro)
        for i, rom in enumerate(bin_roms):
            log(f"[{i+1}/{len(bin_roms)}] Convertendo {rom['name']} ({rom['size']//1024//1024}MB)...")
            ok, msg = convert_bin_to_chd(rom)
            if ok:
                success_count += 1
                saved = rom["size"] // 2  # estimativa
                saved_bytes += saved
                log(f"  -> {msg}")
                state["converted"].append({"name": rom["name"], "size": rom["size"], "time": datetime.now().isoformat()})
            else:
                fail_count += 1
                log(f"  -> FAIL: {msg}")
                state["failed"].append({"name": rom["name"], "error": msg, "time": datetime.now().isoformat()})
            
            # Salvar estado a cada 10 conversoes
            if (i + 1) % 10 == 0:
                state["total_saved"] = state.get("total_saved", 0) + saved_bytes
                save_convert_state(state)
                elapsed = time.time() - t0
                rate = success_count / elapsed if elapsed > 0 else 0
                eta = (len(bin_roms) - i - 1) / rate if rate > 0 else 0
                log(f"  Progresso: {success_count} OK, {fail_count} FAIL, {saved_bytes//1024//1024}MB salvos, ETA: {eta/60:.0f}min")
    
    elapsed = time.time() - t0
    state["total_saved"] = state.get("total_saved", 0) + saved_bytes
    save_convert_state(state)
    
    log("=" * 60)
    log(f"CONCLUIDO: {success_count} convertidos, {fail_count} falhas")
    log(f"Tempo: {elapsed/60:.1f}min")
    log(f"Espaco economizado (estimado): {saved_bytes//1024//1024//1024}GB")
    log(f"Total acumulado: {state['total_saved']//1024//1024//1024}GB")

if __name__ == "__main__":
    main()
