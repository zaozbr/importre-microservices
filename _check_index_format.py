"""Verifica formato dos índices archive."""
import json

for name in ["archive_jp_public_index.json", "archive_jp_index.json", "archive_name_index.json"]:
    p = f"D:\\roms\\library\\roms\\_importre_state\\{name}"
    d = json.load(open(p, "r", encoding="utf-8"))
    print(f"\n=== {name} ({len(d)} entradas) ===")
    for k, v in list(d.items())[:3]:
        print(f"  key={k!r}")
        print(f"  val={v!r}"[:200])
        print()

# Verificar queue serials vs index keys
q = json.load(open("D:\\roms\\library\\roms\\_importre_state\\queue.json", "r", encoding="utf-8"))
pending_serials = [item.get("serial","") if isinstance(item,dict) else str(item) for item in q.get("queue",[])[:20]]
print(f"\n=== Primeiros 20 serials pending ===")
for s in pending_serials:
    print(f"  {s!r}")

# Verificar match
archive_index = {}
for name in ["archive_jp_public_index.json", "archive_jp_index.json", "archive_name_index.json"]:
    p = f"D:\\roms\\library\\roms\\_importre_state\\{name}"
    archive_index.update(json.load(open(p, "r", encoding="utf-8")))

matches = [s for s in pending_serials if s in archive_index]
print(f"\n=== Match: {len(matches)}/20 ===")
for s in matches:
    print(f"  {s} -> {archive_index[s]!r}"[:150])
