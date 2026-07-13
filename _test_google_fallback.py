import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from importre import SiteNavigator, make_search_queries
import json

nav = SiteNavigator.__new__(SiteNavigator)

with open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8") as f:
    q = json.load(f)

pending = q.get("queue", [])
# Pegar alguns itens interessantes
serials = [
    ("BREW-047", "Sonic the Hedgehog PSX (mini Ikuzo)"),
    ("SLPS-02273", "Guilty Gear Fukkokuban [Reprint]"),
    ("SLUS-00592", "Resident Evil 2 [Claire Disc]"),
    ("SLPS-91513", "Samurai Spirits IV - Amakusa's Revenge Special"),
    ("SLPS-03253", "Slot! Pro 3"),
]

for serial, name in serials:
    queries = make_search_queries(name, serial)
    print(f"\n=== {serial} | {name} ===")
    print("queries:", queries)
    for q in queries[:2]:
        try:
            result, detail = nav.search_google(q, serial, name)
            print(f"  query='{q}' -> {result} | {detail}")
            if result:
                break
        except Exception as e:
            print(f"  query='{q}' -> ERRO: {e}")
