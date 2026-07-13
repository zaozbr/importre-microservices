"""Testa archive.org com cookies de sessão autenticada.
Compara velocidade: anônimo vs autenticado.
Verifica se coleções restritas (psx-pal-chd-zstd) ficam acessíveis.
"""
import requests
import time
import json
import os

STATE = r"D:\roms\library\roms\_importre_state"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Cookies de sessão fornecidos pelo usuário
COOKIES = {
    "logged-in-sig": "1815424048%201783888048%20NdcQZOzCA4CB%2BcoaGKXMv8yc%2FQ0uKS0DS7NHsVPyFUzCWjdaAjvSnGTdPdq6DwibaBL1t1%2BX001Lp626v%2BnwpQd6OcSm3ooULfGMPlxfQwIWKJWo9cV906yT6IRVmZOrso8y0nUYy%2BiuoC6xLYaXww3uiRYjdElmQJYDarrLK3PEx88JZfG4NXZTXRKvFD74XXWVsftXlRoU6fyfRkPmcExzl9HK1%2FloDawy1Nydw2ChC3v9HMqejk0iqMc0k21ZK0HJs9ofXsmjMnacziSSD1ZgxOKp8uO5AQKtZxlKEplK27uEvzq5PoUsJv7Kfsh7gZp1cilR2sW3c03iP8roGw%3D%3D",
    "logged-in-user": "zaozao2%40gmail.com",
}

# 1. Verificar se login é válido
print("=" * 70)
print("1. VERIFICANDO SE SESSÃO É VÁLIDA")
print("=" * 70)

try:
    resp = requests.get("https://archive.org/account/", cookies=COOKIES, 
                       timeout=15, headers=HEADERS, allow_redirects=False)
    print(f"  /account/: status={resp.status_code}")
    if resp.status_code == 200:
        print("  Sessão VÁLIDA! ✅")
    elif resp.status_code in (301, 302):
        print(f"  Redirect para: {resp.headers.get('Location', '?')}")
        print("  Sessão pode estar expirada")
    else:
        print(f"  Status inesperado: {resp.status_code}")
except Exception as e:
    print(f"  ERRO: {e}")

# 2. Buscar S3 keys (para auth IA-S3)
print("\n" + "=" * 70)
print("2. BUSCANDO S3 KEYS (IA-S3 auth)")
print("=" * 70)

try:
    resp = requests.get("https://archive.org/account/s3.php", cookies=COOKIES,
                       timeout=15, headers=HEADERS)
    print(f"  /account/s3.php: status={resp.status_code}")
    if resp.status_code == 200:
        # Procurar por S3 access key e secret key no HTML
        import re
        # Pattern: accesskey e secret key em campos input ou texto
        access_match = re.search(r'(?:access|s3_access)["\s:=]+([A-Za-z0-9]{10,20})', resp.text, re.IGNORECASE)
        secret_match = re.search(r'(?:secret|s3_secret)["\s:=]+([A-Za-z0-9]{20,})', resp.text, re.IGNORECASE)
        
        if access_match:
            print(f"  Access key encontrada: {access_match.group(1)}")
        if secret_match:
            print(f"  Secret key encontrada: {secret_match.group(1)[:8]}...")
        
        # Salvar HTML para análise
        with open(os.path.join(STATE, "archive_s3_page.html"), "w", encoding="utf-8") as f:
            f.write(resp.text)
        print(f"  HTML salvo em archive_s3_page.html ({len(resp.text)} chars)")
        
        # Procurar por padrões mais específicos
        # Archive.org S3 keys: access key é alfanumérico curto, secret é longo
        keys = re.findall(r'value="([A-Za-z0-9+/=]{10,})"', resp.text)
        if keys:
            print(f"  Possíveis keys em value=\"\": {len(keys)}")
            for k in keys[:5]:
                print(f"    {k[:20]}... (len={len(k)})")
except Exception as e:
    print(f"  ERRO: {e}")

# 3. Testar coleções restritas COM cookies
print("\n" + "=" * 70)
print("3. COLEÇÕES RESTRITAS COM COOKIES (psx-pal-chd-zstd)")
print("=" * 70)

test_urls = [
    ("psx-pal-chd-zstd (restrita)", "https://archive.org/download/psx-pal-chd-zstd/pal/All%20Star%20Boxing%20(Europe).chd"),
    ("Redump (403 antes)", "https://archive.org/download/Redump_PSX_2021_06_04_A_C/A%20IV%20Evolution%20(Japan).zip"),
    ("psx-ntscj-chd-zstd", "https://archive.org/download/psx-ntscj-chd-zstd/ntscj/Lightning%20Legend%20-%20Daigo%20no%20Daibouken%20(Japan).chd"),
    ("CuratedPSXRedumpCHDs", "https://archive.org/download/CuratedPSXRedumpCHDs/Simple%201500%20Series%20Vol.%2011%20-%20The%20Pinball%20-%203D%20(Japan).chd"),
]

for name, url in test_urls:
    # Sem cookies
    try:
        resp = requests.head(url, timeout=15, headers=HEADERS, allow_redirects=True)
        status_no_auth = resp.status_code
        size_no_auth = resp.headers.get("Content-Length", "?")
    except Exception as e:
        status_no_auth = f"ERRO: {str(e)[:50]}"
        size_no_auth = "?"
    
    # Com cookies
    try:
        resp = requests.head(url, timeout=15, headers=HEADERS, cookies=COOKIES, allow_redirects=True)
        status_auth = resp.status_code
        size_auth = resp.headers.get("Content-Length", "?")
    except Exception as e:
        status_auth = f"ERRO: {str(e)[:50]}"
        size_auth = "?"
    
    print(f"\n  {name}:")
    print(f"    Sem auth: status={status_no_auth} size={size_no_auth}")
    print(f"    Com auth: status={status_auth} size={size_auth}")

# 4. Testar velocidade COM cookies (5MB)
print("\n" + "=" * 70)
print("4. VELOCIDADE COM COOKIES (5MB)")
print("=" * 70)

for name, url in test_urls[:3]:  # primeiros 3
    try:
        t0 = time.time()
        resp = requests.get(url, headers={**HEADERS, "Range": "bytes=0-5242880"},
                           cookies=COOKIES, stream=True, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=256*1024):
            downloaded += len(chunk)
        elapsed = time.time() - t0
        speed = downloaded / elapsed if elapsed > 0 else 0
        final_host = resp.url.split("/")[2] if "://" in resp.url else "?"
        print(f"  {name}: {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s (host={final_host})")
    except Exception as e:
        print(f"  {name}: ERRO — {str(e)[:120]}")

# 5. Salvar cookies para uso pelo aria2c
print("\n" + "=" * 70)
print("5. SALVANDO COOKIES PARA ARIA2C")
print("=" * 70)

# aria2c usa formato Netscape cookies.txt
# Formato: domain	flag	path	secure	expiration	name	value
cookie_file = os.path.join(STATE, "archive_cookies.txt")
expiration = "1899999999"  # timestamp futuro distante

with open(cookie_file, "w") as f:
    f.write("# Netscape HTTP Cookie File\n")
    f.write("# Para uso com aria2c --load-cookies\n")
    f.write(f".archive.org\tTRUE\t/\tTRUE\t{expiration}\tlogged-in-sig\t{COOKIES['logged-in-sig']}\n")
    f.write(f".archive.org\tTRUE\t/\tTRUE\t{expiration}\tlogged-in-user\t{COOKIES['logged-in-user']}\n")

print(f"  Cookies salvos em: {cookie_file}")
print(f"  Usar no aria2c: --load-cookies={cookie_file}")

# Salvar também em JSON para o importre
json.dump(COOKIES, open(os.path.join(STATE, "archive_session.json"), "w", encoding="utf-8"), indent=2)
print(f"  Cookies JSON salvos em: archive_session.json")
