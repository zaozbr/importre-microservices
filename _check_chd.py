import requests, json
r = requests.get('http://127.0.0.1:8766/api/collection', timeout=10)
d = r.json()
print(f"Total games: {d.get('total_games', 0)}")
sc = d.get('status_counts', {})
print(f"Convertidos (CHD): {sc.get('converted', 0)}")
print(f"Prontos para converter: {sc.get('ready_to_convert', 0)}")
print(f"Gerado em: {d.get('generated_at', '?')}")
# Calcular progresso
total = d.get('total_games', 0)
conv = sc.get('converted', 0)
if total > 0:
    pct = conv / total * 100
    print(f"Progresso CHD: {pct:.1f}% ({conv}/{total})")
