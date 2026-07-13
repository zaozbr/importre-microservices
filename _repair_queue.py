"""Repara queue.json corrompido (Extra data = escrita concorrente)."""
import json, os, re

p = r"D:\roms\library\roms\_importre_state\queue.json"
with open(p, "r", encoding="utf-8") as f:
    content = f.read()

# Tentar parsear apenas a primeira parte válida
try:
    d = json.loads(content)
    print("JSON válido!")
except json.JSONDecodeError as e:
    print(f"Erro: {e}")
    # Tentar extrair até o último } válido
    # Procurar pelo padrão de fim de objeto JSON
    last_brace = content.rfind("}")
    if last_brace > 0:
        # Tentar parsear até o último } que forma um JSON válido
        for end in range(last_brace, 0, -1):
            if content[end] == "}":
                try:
                    d = json.loads(content[:end+1])
                    print(f"Reparado! Cortou em char {end+1} de {len(content)}")
                    
                    # Salvar backup
                    bak = p + ".bak"
                    os.rename(p, bak)
                    print(f"Backup: {bak}")
                    
                    # Salvar reparado
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(d, f, ensure_ascii=False, indent=2)
                    print(f"Salvo: {p}")
                    
                    # Mostrar estado
                    print(f"\npending: {len(d.get('queue', []))}")
                    print(f"completed: {len(d.get('completed', {}))}")
                    print(f"in_progress: {len(d.get('in_progress', {}))}")
                    print(f"failed: {len(d.get('failed', {}))}")
                    break
                except:
                    continue
