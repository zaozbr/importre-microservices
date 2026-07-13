#!/usr/bin/env python3
"""Confere os 1025 faltantes vs fila do importre e adiciona os que faltam."""
import sys, re, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

PSX = Path(r"D:\roms\library\roms\psx")
FALTANTES = Path(r"D:\roms\library\roms\PSX_Colecao_Faltantes.md")

def extract_serial(name):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', name, re.I)
    return m.group(1).upper() if m else None

# 1. CHDs existentes
chd_serials = set()
for c in PSX.rglob("*.chd"):
    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', c.stem, re.I)
    if m: chd_serials.add(m.group(1).upper())

# 2. Faltantes da lista
faltantes_serials = set()
if FALTANTES.exists():
    content = FALTANTES.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r'([A-Z]{2,4}[-]\d{3,5})', content):
        faltantes_serials.add(m.group(1).upper())

faltantes_sem_chd = faltantes_serials - chd_serials
print(f"Faltantes sem CHD: {len(faltantes_sem_chd)}")

# 3. Fila do importre
try:
    sys.path.insert(0, str(PSX))
    from importre import file_lock, file_unlock, load_json, save_json, QUEUE_PATH
    fl = file_lock()
    try:
        data = load_json(QUEUE_PATH, {})
        queue_serials = set()
        for q in data.get("queue", []):
            s = q.get("serial", "").upper()
            if s: queue_serials.add(s)
        for k in data.get("in_progress", {}).keys(): queue_serials.add(k.upper())
        for k in data.get("completed", {}).keys(): queue_serials.add(k.upper())
        for k in data.get("failed", {}).keys(): queue_serials.add(k.upper())

        na_fila = faltantes_sem_chd & queue_serials
        fora_fila = faltantes_sem_chd - queue_serials
        print(f"Ja na fila do importre: {len(na_fila)}")
        print(f"Fora da fila (precisa adicionar): {len(fora_fila)}")
        print()

        if fora_fila:
            # Extrair nomes da lista de faltantes para os seriais fora da fila
            # Ler o arquivo de faltantes linha por linha
            serial_to_name = {}
            if FALTANTES.exists():
                for line in FALTANTES.read_text(encoding="utf-8", errors="replace").splitlines():
                    m = re.search(r'([A-Z]{2,4}[-]\d{3,5})', line)
                    if m:
                        s = m.group(1).upper()
                        # O nome e o resto da linha apos o serial
                        name = re.sub(r'([A-Z]{2,4}[-]\d{3,5})\s*[-–]\s*', '', line).strip()
                        name = re.sub(r'^.*?\b([A-Z]{2,4}[-]\d{3,5})\b\s*', '', line).strip()
                        serial_to_name[s] = name[:80]

            added = 0
            for serial in sorted(fora_fila):
                name = serial_to_name.get(serial, serial)
                data["queue"].append({
                    "serial": serial, "name": name,
                    "region": "", "section": "", "type": "commercial",
                    "_needs_search": True,
                })
                added += 1
            data["total"] = len(data.get("queue",[])) + len(data.get("in_progress",{})) + len(data.get("completed",{})) + len(data.get("failed",{}))
            save_json(QUEUE_PATH, data)
            print(f"Adicionados ao importre: {added}")

            # Listar primeiros 20
            print()
            print("Primeiros 20 adicionados:")
            for s in sorted(fora_fila)[:20]:
                print(f"  {s}  {serial_to_name.get(s, '')[:50]}")
            if len(fora_fila) > 20:
                print(f"  ... e mais {len(fora_fila)-20}")
        else:
            print("Todos os faltantes ja estao na fila!")

        # Resumo final
        print()
        print(f"=== RESUMO ===")
        print(f"  Faltantes sem CHD:      {len(faltantes_sem_chd)}")
        print(f"  Ja na fila:             {len(na_fila)}")
        print(f"  Adicionados agora:      {len(fora_fila)}")
        print(f"  Total na fila agora:    {len(na_fila) + len(fora_fila)}")
    finally:
        file_unlock(fl)
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()
