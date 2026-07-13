"""Inspeciona HTML da página JP do coolrom para entender paginação."""
import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

resp = requests.get("https://coolrom.com/roms/psx/japan/A/", timeout=15, headers=HEADERS)
print(f"Status: {resp.status_code}, Tamanho: {len(resp.text)} chars")

# Salvar HTML
with open(r"D:\roms\library\roms\psx\_coolrom_jp_sample.html", "w", encoding="utf-8") as f:
    f.write(resp.text)

# Procurar por links de jogos
pattern = re.compile(r'href="(/roms/psx/(\d+)/([^"]+)\.php)"[^>]*>([^<]+)</a>')
matches = pattern.findall(resp.text)
print(f"\nLinks de jogos: {len(matches)}")
for href, gid, slug, name in matches:
    print(f"  {gid}: {name}")

# Procurar por paginação
page_links = re.findall(r'href="([^"]*page[^"]*)"', resp.text, re.IGNORECASE)
print(f"\nLinks de paginação: {len(page_links)}")
for p in page_links[:10]:
    print(f"  {p}")

# Procurar por "Next" ou "More"
next_pattern = re.findall(r'(next|more|page\s*\d+|show\s*more)', resp.text, re.IGNORECASE)
print(f"\nReferências a next/more: {len(next_pattern)}")

# Procurar por AJAX/JavaScript que carrega mais
ajax_pattern = re.findall(r'(ajax|loadMore|fetch|XMLHttpRequest|\.json|api/)', resp.text, re.IGNORECASE)
print(f"\nAJAX/fetch: {len(ajax_pattern)}")

# Procurar por tabelas
tr_count = resp.text.count("<tr")
print(f"\nTotal <tr>: {tr_count}")

# Mostrar trechos com "roms/psx/"
idx = 0
count = 0
while count < 5:
    idx = resp.text.find("roms/psx/", idx)
    if idx == -1:
        break
    context = resp.text[max(0,idx-50):idx+100].replace("\n", " ")
    print(f"  ...{context}...")
    idx += 10
    count += 1

# Verificar se há select/option com letras
select_pattern = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]+)</option>', resp.text)
print(f"\nOptions: {len(select_pattern)}")
for val, text in select_pattern[:20]:
    print(f"  {val}: {text}")
