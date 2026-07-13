"""Inspeciona HTML real do coolrom para entender estrutura e melhorar scraping."""
import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Buscar página principal de PSX
resp = requests.get("https://coolrom.com/roms/psx/", timeout=15, headers=HEADERS)
print(f"Status: {resp.status_code}")
print(f"Tamanho: {len(resp.text)} chars")

# Salvar HTML para análise
with open(r"D:\roms\library\roms\psx\_coolrom_sample.html", "w", encoding="utf-8") as f:
    f.write(resp.text)

# Procurar por padrões de jogos
# Pattern 1: links /roms/psx/
links = re.findall(r'href="([^"]*roms/psx/[^"]*)"', resp.text)
print(f"\nLinks /roms/psx/: {len(links)}")
for l in links[:20]:
    print(f"  {l}")

# Pattern 2: procurar por nomes de jogos conhecidos
# SLPS-01157 = "A IV Evolution" — buscar por "Evolution" na página
if "evolution" in resp.text.lower():
    idx = resp.text.lower().find("evolution")
    print(f"\nContexto 'evolution': ...{resp.text[max(0,idx-100):idx+100]}...")

# Pattern 3: procurar por tabelas ou listas de jogos
# CoolROM usa tabelas: <tr><td>...<a href="/roms/psx/{slug}/{id}/">{name}</a>...</td></tr>
tr_pattern = re.findall(r'<tr[^>]*>.*?</tr>', resp.text, re.DOTALL)
print(f"\nLinhas <tr>: {len(tr_pattern)}")
if tr_pattern:
    # Mostrar primeira linha com link
    for tr in tr_pattern[:5]:
        if "roms/psx" in tr:
            clean = re.sub(r'<[^>]+>', ' ', tr).strip()[:100]
            print(f"  TR: {clean}")

# Pattern 4: procurar por divs com classe de jogo
div_pattern = re.findall(r'<div[^>]*class="[^"]*rom[^"]*"[^>]*>.*?</div>', resp.text, re.DOTALL | re.IGNORECASE)
print(f"\nDivs 'rom': {len(div_pattern)}")

# Pattern 5: procurar por data attributes
data_pattern = re.findall(r'data-[a-z]+="[^"]*"', resp.text)
print(f"\nData attributes: {len(data_pattern)}")
for d in data_pattern[:10]:
    print(f"  {d}")

# Verificar se há paginação
page_pattern = re.findall(r'href="([^"]*page[^"]*)"', resp.text)
print(f"\nLinks de paginação: {len(page_pattern)}")
for p in page_pattern[:5]:
    print(f"  {p}")

# Verificar se há busca/search
search_pattern = re.findall(r'(search|query|find)', resp.text, re.IGNORECASE)
print(f"\nReferências a search: {len(search_pattern)}")

# Procurar por JavaScript que carrega jogos
js_pattern = re.findall(r'(ajax|loadGames|fetchGames|gameList)', resp.text, re.IGNORECASE)
print(f"JS game loading: {len(js_pattern)}")
