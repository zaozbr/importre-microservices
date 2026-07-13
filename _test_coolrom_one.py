import json, re, requests
from bs4 import BeautifulSoup
from pathlib import Path

STATE_DIR = Path('D:/roms/library/roms/_importre_state')
serial = 'SLPM-86908'
name = 'DX Hyakunin Issyu'

req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
idx = json.loads((STATE_DIR / 'coolrom_index.json').read_text(encoding='utf-8'))
word_index = idx['word_index']
cr_data = idx['cr_data']

name_clean = re.sub(r"\(.*?\)", "", name).strip()
name_lower = name_clean.lower()
name_words = set(w for w in re.sub(r"[^a-z0-9\s]", "", name_lower).split() if len(w) > 2)
print('words:', name_words)

candidates = set()
for w in name_words:
    candidates.update(word_index.get(w, []))
print('candidates:', len(candidates))

scored = []
for ck in candidates:
    entry = cr_data.get(ck)
    if not entry:
        continue
    cr_norm = entry.get('norm', '')
    cr_words = set(w for w in cr_norm.split() if len(w) > 2)
    overlap = len(name_words & cr_words)
    score = overlap / max(len(name_words), 1)
    if score >= 0.5:
        if entry.get('jp'):
            score += 0.1
        scored.append((score, entry))
scored.sort(key=lambda x: x[0], reverse=True)
print('top scored:', [(s, e['name']) for s, e in scored[:5]])

for score, entry in scored[:3]:
    detail_url = f"https://coolrom.com{entry['url']}"
    print(f'Trying {detail_url} (score {score})')
    try:
        r = requests.get(detail_url, timeout=10, headers=req_headers)
        print(f'  status {r.status_code}, len {len(r.text)}')
        serial_norm = serial.upper().replace('-', '')
        serial_found = serial_norm in r.text.upper().replace('-', '')
        print(f'  serial found: {serial_found}')
        soup = BeautifulSoup(r.text, 'lxml')
        for a in soup.find_all('a', href=True):
            if 'dl.coolrom.com' in a['href']:
                print(f'  FOUND: {a["href"]}')
                break
    except Exception as e:
        print(f'  error: {e}')
