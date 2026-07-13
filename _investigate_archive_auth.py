"""Investiga autenticação do archive.org:
1. Verifica quais coleções retornam 403/401/auth failed
2. Testa se login com email/senha resolve (IA-S3 auth)
3. Verifica se há cookies de sessão válidos
4. Compara velocidade autenticado vs anônimo
"""
import requests
import time
import json
import os
import re

STATE = r"D:\roms\library\roms\_importre_state"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. Testar coleções que falharam no log
print("=" * 70)
print("1. TESTANDO COLEÇÕES QUE FALHARAM (403/auth/500)")
print("=" * 70)

test_collections = {
    "psx-pal-chd-zstd": "http://archive.org/download/psx-pal-chd-zstd/pal/All%20Star%20Boxing%20(Europe).chd",
    "Redump_PSX_2021_06_04_A_C": "http://archive.org/download/Redump_PSX_2021_06_04_A_C/A%20IV%20Evolution%20(Japan).zip",
    "psx-ntscj-chd-zstd": "http://archive.org/download/psx-ntscj-chd-zstd/ntscj/Lightning%20Legend%20-%20Daigo%20no%20Daibouken%20(Japan).chd",
    "CuratedPSXRedumpCHDs": "http://archive.org/download/CuratedPSXRedumpCHDs/Simple%201500%20Series%20Vol.%2011%20-%20The%20Pinball%20-%203D%20(Japan).chd",
    "psx-chd-roms-m": "http://archive.org/download/psx-chd-roms-m/Marl%20Oukoku%20no%20Ningyouhime%20-%20The%20Adventure%20of%20Puppet%20Princess%20(Japan).chd",
}

results = {}
for coll, url in test_collections.items():
    try:
        # HEAD request para verificar status sem baixar
        resp = requests.head(url, timeout=15, headers=HEADERS, allow_redirects=True)
        status = resp.status_code
        final_url = resp.url
        size = resp.headers.get("Content-Length", "?")
        accept_ranges = resp.headers.get("Accept-Ranges", "none")
        
        print(f"\n  {coll}:")
        print(f"    Status: {status}")
        print(f"    Size: {size}")
        print(f"    Accept-Ranges: {accept_ranges}")
        print(f"    Final URL: {final_url[:80]}")
        
        results[coll] = {"status": status, "size": size, "accept_ranges": accept_ranges}
    except Exception as e:
        print(f"\n  {coll}: ERRO — {e}")
        results[coll] = {"status": "error", "error": str(e)}

# 2. Verificar metadata das coleções (API do archive.org)
print("\n" + "=" * 70)
print("2. METADATA DAS COLEÇÕES (API archive.org)")
print("=" * 70)

for coll in test_collections.keys():
    try:
        metadata_url = f"http://archive.org/metadata/{coll}"
        resp = requests.get(metadata_url, timeout=15, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            is_dark = data.get("metadata", {}).get("is_dark", "false")
            access = data.get("metadata", {}).get("access", "public")
            server = data.get("server")
            d1 = data.get("d1")
            dir_ = data.get("dir")
            files_count = len(data.get("files", []))
            
            print(f"\n  {coll}:")
            print(f"    access: {access}")
            print(f"    is_dark: {is_dark}")
            print(f"    server: {server}")
            print(f"    d1: {d1}")
            print(f"    dir: {dir_}")
            print(f"    files: {files_count}")
            
            results[coll].update({
                "access": access,
                "is_dark": is_dark,
                "server": server,
                "d1": d1,
                "dir": dir_,
            })
        else:
            print(f"\n  {coll}: metadata HTTP {resp.status_code}")
    except Exception as e:
        print(f"\n  {coll}: metadata ERRO — {e}")

# 3. Verificar se há cookies de sessão do archive.org
print("\n" + "=" * 70)
print("3. VERIFICANDO COOKIES/SESSÃO DO ARCHIVE.ORG")
print("=" * 70)

# Verificar se há arquivo de cookies
cookie_paths = [
    os.path.join(STATE, "archive_cookies.txt"),
    os.path.join(STATE, "archive_session.json"),
    os.path.expanduser("~/.archive.org/cookies.txt"),
]

for p in cookie_paths:
    if os.path.exists(p):
        print(f"  Encontrado: {p}")
        with open(p, "r") as f:
            content = f.read()[:200]
        print(f"    Conteúdo: {content}")
    else:
        print(f"  Não encontrado: {p}")

# 4. Testar login no archive.org (se houver credenciais)
print("\n" + "=" * 70)
print("4. TESTAR LOGIN NO ARCHIVE.ORG")
print("=" * 70)

# Archive.org usa IA-S3 auth: email + senha -> cookie de sessão
# Endpoint: https://archive.org/account/login
# Mas precisamos de credenciais — verificar se há config
config_path = os.path.join(STATE, "archive_config.json")
if os.path.exists(config_path):
    config = json.load(open(config_path, "r", encoding="utf-8"))
    print(f"  Config encontrada: {list(config.keys())}")
else:
    print("  Nenhuma config de archive.org encontrada")
    print("  Para autenticar, precisamos de email/senha do archive.org")
    print("  Login gratuito em: https://archive.org/account/signup")

# 5. Verificar se archive.org tem rate limit documentado
print("\n" + "=" * 70)
print("5. RATE LIMIT DO ARCHIVE.ORG")
print("=" * 70)

# Testar velocidade real de uma coleção que funciona
print("\n  Testando velocidade real (5MB de CuratedPSXRedumpCHDs)...")
test_url = "http://archive.org/download/CuratedPSXRedumpCHDs/Simple%201500%20Series%20Vol.%2011%20-%20The%20Pinball%20-%203D%20(Japan).chd"
try:
    t0 = time.time()
    resp = requests.get(test_url, headers={**HEADERS, "Range": "bytes=0-5242880"}, 
                       stream=True, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    downloaded = 0
    for chunk in resp.iter_content(chunk_size=256*1024):
        downloaded += len(chunk)
    elapsed = time.time() - t0
    speed = downloaded / elapsed if elapsed > 0 else 0
    print(f"  CuratedPSXRedumpCHDs: {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s")
except Exception as e:
    print(f"  ERRO: {e}")

# Testar psx-ntscj-chd-zstd (que tinha 500 intermitente)
print("\n  Testando psx-ntscj-chd-zstd (5MB)...")
test_url2 = "http://archive.org/download/psx-ntscj-chd-zstd/ntscj/Lightning%20Legend%20-%20Daigo%20no%20Daibouken%20(Japan).chd"
try:
    t0 = time.time()
    resp = requests.get(test_url2, headers={**HEADERS, "Range": "bytes=0-5242880"},
                       stream=True, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    downloaded = 0
    for chunk in resp.iter_content(chunk_size=256*1024):
        downloaded += len(chunk)
    elapsed = time.time() - t0
    speed = downloaded / elapsed if elapsed > 0 else 0
    print(f"  psx-ntscj-chd-zstd: {downloaded/1024/1024:.1f}MB em {elapsed:.1f}s = {speed/1024/1024:.2f}MB/s")
except Exception as e:
    print(f"  ERRO: {e}")

# 6. Verificar se há múltiplos servidores espelho (CDN)
print("\n" + "=" * 70)
print("6. SERVIDORES ESPELHO (CDN) DO ARCHIVE.ORG")
print("=" * 70)

# Archive.org redireciona para dnXXX.ca.archive.org ou iaXXX.us.archive.org
# Cada servidor pode ter rate limit independente
for coll in ["psx-ntscj-chd-zstd", "CuratedPSXRedumpCHDs"]:
    try:
        metadata_url = f"http://archive.org/metadata/{coll}"
        resp = requests.get(metadata_url, timeout=15, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            server = data.get("server", "?")
            d1 = data.get("d1", "?")
            d2 = data.get("d2", "?")
            print(f"  {coll}: server={server} d1={d1} d2={d2}")
    except:
        pass

# Salvar resultados
json.dump(results, open(os.path.join(STATE, "archive_auth_test.json"), "w", encoding="utf-8"), indent=2)
print(f"\nResultados salvos em archive_auth_test.json")
