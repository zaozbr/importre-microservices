"""
Tenta acessar archive.org via:
1. Proxies HTTP publicos gratuitos
2. Cloudflare WARP (se disponivel)
3. DNS-over-HTTPS para descartar bloqueio de DNS
"""
import requests, time, socket, subprocess, os, json

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("=== ARCHIVE.ORG - TENTATIVAS DE ACESSO ALTERNATIVO ===\n")

# 1. Verificar se Cloudflare WARP esta instalado
print("1. Cloudflare WARP")
warp_paths = [
    r'C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe',
    r'C:\Program Files (x86)\Cloudflare\Cloudflare WARP\warp-cli.exe',
    r'%LOCALAPPDATA%\Programs\Cloudflare\Cloudflare WARP\warp-cli.exe',
]
warp_found = None
for p in warp_paths:
    expanded = os.path.expandvars(p)
    if os.path.exists(expanded):
        warp_found = expanded
        break

if warp_found:
    print(f"   Encontrado: {warp_found}")
    try:
        result = subprocess.run([warp_found, 'status'], capture_output=True, text=True, timeout=10)
        print(f"   Status: {result.stdout.strip()}")
    except Exception as e:
        print(f"   ERRO: {e}")
else:
    print("   WARP nao encontrado. Sera que baixamos? (36MB)")
    # Verificar se winget esta disponivel
    try:
        result = subprocess.run(['winget', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"   winget disponivel: {result.stdout.strip()}")
            print("   -> Pode instalar WARP com: winget install Cloudflare.WARP")
        else:
            print("   winget nao disponivel")
    except:
        print("   winget nao disponivel")

# 2. Testar com proxies HTTP publicos
print("\n2. Proxies HTTP publicos gratuitos")
# Lista de proxies publicos (podem estar offline - testar varios)
public_proxies = [
    'http://47.88.31.164:8080',
    'http://103.152.112.162:80',
    'http://167.172.238.6:80',
    'http://51.79.144.52:80',
    'http://198.199.122.231:80',
    'http://205.169.201.78:80',
    'http://107.151.182.163:80',
    'http://45.42.58.246:80',
]

working_proxy = None
for proxy_url in public_proxies:
    try:
        t0 = time.time()
        proxies = {'http': proxy_url, 'https': proxy_url}
        r = requests.get('https://archive.org/advancedsearch.php?q=test&output=json', 
                        proxies=proxies, timeout=10, headers=HEADERS)
        elapsed = time.time() - t0
        if r.status_code == 200:
            print(f"   OK! {proxy_url} -> {r.status_code} em {elapsed:.1f}s")
            working_proxy = proxy_url
            break
        else:
            print(f"   {proxy_url} -> {r.status_code} em {elapsed:.1f}s")
    except Exception as e:
        pass  # Nao imprimir erros para nao poluir

if not working_proxy:
    print("   Nenhum proxy publico funcionou")

# 3. DNS-over-HTTPS - verificar se o DNS esta sendo manipulado
print("\n3. DNS-over-HTTPS (verificar manipulacao de DNS)")
try:
    # Usar Cloudflare DNS-over-HTTPS
    r = requests.get('https://cloudflare-dns.com/dns-query?name=archive.org&type=A',
                     headers={'Accept': 'application/dns-json'}, timeout=10)
    if r.status_code == 200:
        data = r.json()
        answers = data.get('Answer', [])
        print(f"   DNS via Cloudflare: {answers}")
        for a in answers:
            if a.get('type') == 1:  # A record
                print(f"   IP real do archive.org: {a.get('data')}")
except Exception as e:
    print(f"   ERRO: {e}")

# Comparar com DNS local
print("\n4. Comparar DNS local vs Cloudflare")
try:
    local_ips = socket.getaddrinfo('archive.org', 443, socket.AF_INET)
    local_ip = local_ips[0][4][0]
    print(f"   DNS local: {local_ip}")
except Exception as e:
    print(f"   DNS local ERRO: {e}")

# 5. Testar se o problema e rota (traceroute)
print("\n5. Traceroute para archive.org (primeiros 10 saltos)")
try:
    result = subprocess.run(['tracert', '-d', '-h', '10', '-w', '2000', 'archive.org'],
                           capture_output=True, text=True, timeout=60)
    for line in result.stdout.split('\n'):
        if line.strip():
            print(f"   {line.rstrip()}")
except Exception as e:
    print(f"   ERRO: {e}")

# 6. Testar se outros sites da mesma CDN (207.241.x.x) funcionam
print("\n6. Testar outros sites no range 207.241.x.x")
other_sites = [
    ('archive.org', '207.241.224.2'),
    ('www.archive.org', None),
    ('web.archive.org', None),
    ('openlibrary.org', None),
    ('archive-it.org', None),
]
for host, expected_ip in other_sites:
    try:
        ips = socket.getaddrinfo(host, 443, socket.AF_INET)
        ip = ips[0][4][0]
        t0 = time.time()
        sock = socket.create_connection((ip, 443), timeout=5)
        elapsed = time.time() - t0
        print(f"   {host:25s} -> {ip:15s} OK {elapsed:.2f}s")
        sock.close()
    except Exception as e:
        print(f"   {host:25s} -> ERRO {str(e)[:50]}")

# 7. Verificar se ha firewall bloqueando
print("\n7. Verificar firewall do Windows")
try:
    result = subprocess.run(['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all', 'dir=out'],
                           capture_output=True, text=True, timeout=10)
    # Procurar regras que mencionam archive
    lines = result.stdout.split('\n')
    for i, line in enumerate(lines):
        if 'archive' in line.lower():
            # Imprimir contexto
            for j in range(max(0, i-2), min(len(lines), i+5)):
                print(f"   {lines[j].rstrip()}")
            print("   ---")
except Exception as e:
    print(f"   ERRO: {e}")

# 8. Testar com tunnel SSH via serveo.net (gratis, sem registro)
print("\n8. Testar serveo.net (tunnel SSH gratuito)")
try:
    # serveo.net permite tunneling SSH sem registro
    # ssh -R 80:localhost:8080 serveo.net
    # Mas precisamos de um servidor local primeiro
    # Por ora, apenas verificar se serveo.net responde
    r = requests.get('https://serveo.net/', timeout=10, headers=HEADERS)
    print(f"   serveo.net: {r.status_code}")
except Exception as e:
    print(f"   serveo.net: {str(e)[:80]}")

# 9. Verificar se pip pode instalar cloudflared (tunnel do Cloudflare)
print("\n9. Verificar cloudflared (tunnel do Cloudflare)")
try:
    result = subprocess.run(['where', 'cloudflared'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print(f"   cloudflared encontrado: {result.stdout.strip()}")
    else:
        print("   cloudflared nao encontrado")
        # Verificar se pode ser instalado via winget
        result2 = subprocess.run(['winget', 'search', 'cloudflare.cloudflared'], capture_output=True, text=True, timeout=15)
        print(f"   winget search: {result2.stdout[:200]}")
except Exception as e:
    print(f"   ERRO: {e}")

print(f"\n=== RESULTADO ===")
if working_proxy:
    print(f"PROXY FUNCIONANDO: {working_proxy}")
    print("Use este proxy no _deep_search.py para acessar archive.org")
else:
    print("Nenhum proxy funcionou. Recomendacoes:")
    print("1. Instalar Cloudflare WARP: winget install Cloudflare.WARP")
    print("2. Ou instalar cloudflared e criar tunnel")
    print("3. Ou usar VPN gratuita como ProtonVPN")
