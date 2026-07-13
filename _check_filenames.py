"""Verifica formato dos nomes de arquivos nas coleções."""
import json, urllib.request

# Verificar psx-ntscj-chd-zstd (2977 arquivos)
url = "https://archive.org/metadata/psx-ntscj-chd-zstd"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode("utf-8"))

files = data.get("files", [])
print(f"Total arquivos: {len(files)}")
print("\nPrimeiros 10 arquivos (.chd):")
count = 0
for f in files:
    fname = f.get("name", "")
    if fname.endswith(".chd"):
        print(f"  {fname} (size={f.get('size','?')})")
        count += 1
        if count >= 10:
            break

# Verificar estrutura de diretórios
print("\nDiretórios (primeiros 5):")
dirs = set()
for f in files:
    fname = f.get("name", "")
    if "/" in fname:
        dirs.add(fname.split("/")[0])
for d in sorted(dirs)[:5]:
    print(f"  {d}/")

# Verificar psx-pal-chd-zstd
print("\n\npsx-pal-chd-zstd:")
url2 = "https://archive.org/metadata/psx-pal-chd-zstd"
req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req2, timeout=30) as resp2:
    data2 = json.loads(resp2.read().decode("utf-8"))

files2 = data2.get("files", [])
print(f"Total: {len(files2)}")
count = 0
for f in files2:
    fname = f.get("name", "")
    if fname.endswith(".chd") or fname.endswith(".7z"):
        print(f"  {fname}")
        count += 1
        if count >= 10:
            break
