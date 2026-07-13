"""Repara queue.json — versão robusta."""
import json, os

p = r"D:\roms\library\roms\_importre_state\queue.json"
with open(p, "r", encoding="utf-8") as f:
    content = f.read()

print(f"Total chars: {len(content)}")
print(f"Últimos 200 chars: {repr(content[-200:])}")

# O problema é "Extra data" — provavelmente há dois objetos JSON concatenados
# ou caracteres extras no final

# Estratégia: usar json.JSONDecoder para parsear apenas o primeiro objeto
decoder = json.JSONDecoder()
try:
    obj, idx = decoder.raw_decode(content)
    print(f"\nParseado com sucesso! Objeto termina em char {idx}")
    print(f"Resto: {repr(content[idx:idx+100])}")
    
    # Salvar backup
    bak = p + ".corrupt"
    if not os.path.exists(bak):
        os.rename(p, bak)
    
    # Salvar reparado
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    
    print(f"\nReparado e salvo!")
    print(f"pending: {len(obj.get('queue', []))}")
    print(f"completed: {len(obj.get('completed', {}))}")
    print(f"in_progress: {len(obj.get('in_progress', {}))}")
    print(f"failed: {len(obj.get('failed', {}))}")
except Exception as e:
    print(f"raw_decode falhou: {e}")
    
    # Último recurso: tentar encontrar o fim do objeto
    depth = 0
    in_string = False
    escape = False
    end_idx = 0
    for i, c in enumerate(content):
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break
    
    if end_idx > 0:
        print(f"Encontrado fim do objeto em char {end_idx}")
        try:
            obj = json.loads(content[:end_idx])
            bak = p + ".corrupt"
            if not os.path.exists(bak):
                os.rename(p, bak)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            print("Reparado!")
            print(f"pending: {len(obj.get('queue', []))}")
            print(f"completed: {len(obj.get('completed', {}))}")
            print(f"in_progress: {len(obj.get('in_progress', {}))}")
            print(f"failed: {len(obj.get('failed', {}))}")
        except Exception as e2:
            print(f"Falhou: {e2}")
