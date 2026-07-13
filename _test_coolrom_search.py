import json
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path

STATE_DIR = Path('D:/roms/library/roms/_importre_state')

def search_coolrom(name, serial):
    req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    index_path = STATE_DIR / "coolrom_index.json"
    if not index_path.exists():
        return None, "coolrom: indice nao encontrado"
    try:
        idx = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"coolrom: erro ao carregar indice: {e}"
    word_index = idx.get("word_index", {})
    cr_data = idx.get("cr_data", {})

    name_clean = re.sub(r"\(.*?\)", "", name).strip()
    name_lower = name_clean.lower()
    name_words = set(w for w in re.sub(r"[^a-z0-9\s]", "", name_lower).split() if len(w) > 2)
    print(f"Name: {name}, words: {name_words}")
    if not name_words:
        return None, "coolrom: nome muito curto"

    candidates = set()
    for w in name_words:
        cands = word_index.get(w, [])
        print(f"  word '{w}' -> {len(cands)} candidates")
        candidates.update(cands)
    if not candidates:
        return None, "coolrom: sem candidatos no indice"
    print(f"Total candidates: {len(candidates)}")

    scored = []
    for ck in candidates:
        entry = cr_data.get(ck)
        if not entry:
            continue
        cr_norm = entry.get("norm", "")
        cr_words = set(w for w in cr_norm.split() if len(w) > 2)
        overlap = len(name_words & cr_words)
        score = overlap / max(len(name_words), 1)
        print(f"  candidate {ck}: score={score:.2f}, norm={cr_norm}")
        if score >= 0.5:
            if entry.get("jp"):
                score += 0.1
            scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)

    for score, entry in scored[:3]:
        link_url = entry["url"]
        link_text = entry["name"]
        detail_url = f"https://coolrom.com{link_url}"
        print(f"Trying detail: {detail_url} (score {score:.2f})")
        try:
            resp2 = requests.get(detail_url, timeout=10, headers=req_headers)
            print(f"  status: {resp2.status_code}, len: {len(resp2.text)}")
            if resp2.status_code != 200:
                continue
            page_text = resp2.text
            serial_norm = serial.upper().replace("-", "")
            serial_found = serial_norm in page_text.upper().replace("-", "")
            print(f"  serial {serial} found in page: {serial_found}")
            if not serial_found and score < 0.8:
                continue
            soup2 = BeautifulSoup(page_text, "lxml")
            for a in soup2.find_all("a", href=True):
                href = a["href"]
                if "dl.coolrom.com" in href:
                    print(f"  FOUND: {href}")
                    return ("direct_url", href), f"coolrom: {link_text} ({score:.0%})"
        except Exception as e:
            print(f"  error: {e}")
            continue
    return None, "coolrom: nao encontrado"

# Testar seriais que estavam falhando
for serial, name in [
    ("SLPM-86908", "Minna no Othello [Superlite Gold Series]"),
    ("SLPM-86961", "Housoukyouku, The - Satelli TV [Major Wave Series]"),
    ("SLPM-86867", "Simple 1500 Series Hello Kitty Vol.02 - Hello Kitty Illust Puzzle"),
    ("SLPM-86963", "DX Jinsei Game - The Game of Life"),
]:
    print(f"\n=== {serial} {name} ===")
    result, detail = search_coolrom(name, serial)
    print(f"Result: {result}")
    print(f"Detail: {detail}")
