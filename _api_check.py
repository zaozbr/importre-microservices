"""Verifica resposta da API do importre."""
import urllib.request, json

# Tentar diferentes endpoints
for endpoint in ["/api/status", "/api/queue", "/api/downloads", "/status"]:
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:8765{endpoint}", timeout=5)
        data = r.read()
        print(f"{endpoint}: status={r.status}, size={len(data)}")
        if len(data) < 2000:
            print(f"  body: {data.decode('utf-8', errors='replace')[:500]}")
        else:
            # Tentar parsear JSON
            try:
                j = json.loads(data)
                if isinstance(j, dict):
                    print(f"  keys: {list(j.keys())[:10]}")
                    # Mostrar estrutura
                    for k, v in list(j.items())[:5]:
                        if isinstance(v, dict):
                            print(f"  {k}: dict({len(v)} keys)")
                        elif isinstance(v, list):
                            print(f"  {k}: list({len(v)} items)")
                        else:
                            print(f"  {k}: {repr(v)[:80]}")
            except:
                print(f"  não é JSON, primeiros 200 chars: {data[:200]}")
    except Exception as e:
        print(f"{endpoint}: ERRO {e}")
    print()
