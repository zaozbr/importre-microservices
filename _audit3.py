#!/usr/bin/env python3
"""Auditoria detalhada - falhas e BINs sem CHD."""
from pathlib import Path
import os, re

PSX = Path(r"D:\roms\library\roms\psx")
DUP = PSX / "duplicados"

# 1. Categorizar BINs sem CHD na pasta principal
chd_names = set()
for c in PSX.glob("*.chd"):
    chd_names.add(c.stem.lower())

bins_no_chd = []
for f in PSX.glob("*"):
    if f.suffix.lower() in {".bin", ".img", ".iso", ".mdf"}:
        # Verificar se tem CUE correspondente
        cue = f.with_suffix(".cue")
        has_cue = cue.exists()
        # Verificar se ja tem CHD (fuzzy: serial na nome do CHD)
        serial_match = False
        # Extrair serial do nome
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', f.stem, re.I)
        if m:
            serial = m.group(1).upper()
            for cn in chd_names:
                if serial.lower() in cn:
                    serial_match = True
                    break
        if not serial_match:
            bins_no_chd.append((f.name, f.stat().st_size / (1024*1024), has_cue))

# 2. CUEs sem CHD na pasta duplicados
cues_dup_no_chd = []
if DUP.exists():
    for cue in DUP.glob("*.cue"):
        # Verificar se tem BIN correspondente
        content = cue.read_text(encoding="utf-8", errors="replace")
        refs = re.findall(r'FILE\s+"([^"]+)"', content)
        has_bin = False
        for ref in refs:
            bin_path = DUP / ref
            if bin_path.exists():
                has_bin = True
                break
            # Procurar fuzzy
            if not has_bin:
                for b in DUP.glob("*.bin"):
                    if b.stem.lower() in ref.lower() or ref.lower().replace(".bin","") in b.stem.lower():
                        has_bin = True
                        break
        # Verificar se ja tem CHD
        serial = ""
        m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', cue.stem, re.I)
        if m:
            serial = m.group(1).upper()
        has_chd = False
        if serial:
            for cn in chd_names:
                if serial.lower() in cn:
                    has_chd = True
                    break
        if not has_chd:
            cues_dup_no_chd.append((cue.name, has_bin, serial))

# 3. CUEs na pasta principal sem CHD
cues_main_no_chd = []
for cue in PSX.glob("*.cue"):
    content = cue.read_text(encoding="utf-8", errors="replace")
    refs = re.findall(r'FILE\s+"([^"]+)"', content)
    has_bin = False
    for ref in refs:
        bin_path = PSX / ref
        if bin_path.exists():
            has_bin = True
            break
    serial = ""
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', cue.stem, re.I)
    if m:
        serial = m.group(1).upper()
    has_chd = False
    if serial:
        for cn in chd_names:
            if serial.lower() in cn:
                has_chd = True
                break
    if not has_chd:
        cues_main_no_chd.append((cue.name, has_bin, serial))

# 4. Falhas do log
chd_log = PSX / "_chd_convert.log"
fail_categories = {}
if chd_log.exists():
    lines = chd_log.read_text(encoding="utf-8", errors="replace").splitlines()
    # Ultima run
    last_start = 0
    for i, l in enumerate(lines):
        if "=== CHD Converter v2 ===" in l:
            last_start = i
    last_run = lines[last_start:]
    for l in last_run:
        if "FAIL" in l:
            if "couldn" in l and "find bin" in l:
                fail_categories["couldn_t_find_bin"] = fail_categories.get("couldn_t_find_bin", 0) + 1
            elif "INDEX 01" in l:
                fail_categories["index_01"] = fail_categories.get("index_01", 0) + 1
            elif "MODEx" in l:
                fail_categories["modex"] = fail_categories.get("modex", 0) + 1
            elif "muito pequeno" in l:
                fail_categories["muito_pequeno"] = fail_categories.get("muito_pequeno", 0) + 1
            elif "CUE corrompido" in l:
                fail_categories["cue_corrompido"] = fail_categories.get("cue_corrompido", 0) + 1
            elif "CUE sem estrutura" in l:
                fail_categories["cue_sem_estrutura"] = fail_categories.get("cue_sem_estrutura", 0) + 1
            elif "RIFF" in l:
                fail_categories["riff"] = fail_categories.get("riff", 0) + 1
            elif "Permission denied" in l:
                fail_categories["permission_denied"] = fail_categories.get("permission_denied", 0) + 1
            elif "CUE ref nao encontrada" in l:
                fail_categories["cue_ref_nao_encontrada"] = fail_categories.get("cue_ref_nao_encontrada", 0) + 1
            else:
                fail_categories["other"] = fail_categories.get("other", 0) + 1

# === RELATORIO ===
print("=" * 60)
print("  AUDITORIA DETALHADA - FALHAS E GAPS")
print("=" * 60)

print(f"\n--- BINs/IMGs SEM CHD (pasta principal) ---")
print(f"  Total: {len(bins_no_chd)}")
com_cue = sum(1 for _, _, has_cue in bins_no_chd if has_cue)
sem_cue = sum(1 for _, _, has_cue in bins_no_chd if not has_cue)
print(f"  Com CUE (convertiveis): {com_cue}")
print(f"  Sem CUE: {sem_cue}")
# Top 10 maiores
bins_no_chd.sort(key=lambda x: -x[1])
print(f"\n  Maiores BINs sem CHD:")
for name, size, has_cue in bins_no_chd[:10]:
    print(f"    {size:>8.1f}MB  CUE={'S' if has_cue else 'N'}  {name[:60]}")

print(f"\n--- CUEs SEM CHD (pasta principal) ---")
print(f"  Total: {len(cues_main_no_chd)}")
com_bin = sum(1 for _, has_bin, _ in cues_main_no_chd if has_bin)
sem_bin = sum(1 for _, has_bin, _ in cues_main_no_chd if not has_bin)
print(f"  Com BIN (convertiveis): {com_bin}")
print(f"  Sem BIN (precisa download): {sem_bin}")

print(f"\n--- CUEs SEM CHD (duplicados) ---")
print(f"  Total: {len(cues_dup_no_chd)}")
com_bin_dup = sum(1 for _, has_bin, _ in cues_dup_no_chd if has_bin)
sem_bin_dup = sum(1 for _, has_bin, _ in cues_dup_no_chd if not has_bin)
print(f"  Com BIN (convertiveis): {com_bin_dup}")
print(f"  Sem BIN (precisa download): {sem_bin_dup}")

print(f"\n--- CATEGORIAS DE FALHA (ultima run) ---")
total_fails = sum(fail_categories.values())
print(f"  Total falhas: {total_fails}")
for cat, count in sorted(fail_categories.items(), key=lambda x: -x[1]):
    pct = 100 * count / max(total_fails, 1)
    print(f"  {cat:>30}: {count:>3} ({pct:.0f}%)")

print(f"\n--- RESUMO EXECUTIVO ---")
total_chds = len(list(PSX.glob("*.chd"))) + len(list(DUP.glob("*.chd"))) if DUP.exists() else 0
total_convertiveis = com_cue + com_bin + com_bin_dup
total_precisa_download = sem_cue + sem_bin + sem_bin_dup
print(f"  CHDs validos:           {total_chds}")
print(f"  Convertiveis agora:     {total_convertiveis}")
print(f"  Precisam download:      {total_precisa_download}")
print(f"  Falhas (BINs ausentes): {fail_categories.get('couldn_t_find_bin', 0) + fail_categories.get('cue_ref_nao_encontrada', 0)}")
print(f"  Falhas (BINs corrompidos): {fail_categories.get('index_01', 0) + fail_categories.get('muito_pequeno', 0) + fail_categories.get('riff', 0)}")
print("=" * 60)
