"""Testa se archive.org funciona via proxy ou portas alternativas."""
import os, time, requests, subprocess

print("=== ARCHIVE.ORG - TESTE ALTERNATIVOS ===\n")

# 1. Verificar variaveis de proxy
print("1. Variaveis de proxy")
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NO_PROXY', 'no_proxy', 'ALL_PROXY']
for v in proxy_vars:
    val = os.environ.get(v, '')
    if val:
        print(f"   {v} = {val}")
    else:
        print(f"   {v} = (vazio)")

# 2. Verificar configuracao de proxy no Windows
print("\n2. Proxy do Windows (netsh)")
try:
    result = subprocess.run(['netsh', 'winhttp', 'show', 'proxy'], capture_output=True, text=True, timeout=10)
    print(f"   {result.stdout.strip()}")
except Exception as e:
    print(f"   ERRO: {e}")

# 3. Testar outros sites que funcionam para comparar
print("\n3. Comparativo com outros sites (TCP 443)")
import socket
for host in ['archive.org', 'www.archive.org', 'ia801503.us.archive.org', 'coolrom.com', 'github.com', 'google.com']:
    try:
        t0 = time.time()
        sock = socket.create_connection((host, 443), timeout=8)
        elapsed = time.time() - t0
        print(f"   {host:30s} OK  {elapsed:.2f}s")
        sock.close()
    except Exception as e:
        print(f"   {host:30s} ERRO {str(e)[:50]}")

# 4. Testar subdominios do archive.org
print("\n4. Subdominios do archive.org")
for host in ['archive.org', 'www.archive.org', 'ia801503.us.archive.org', 'ia902204.us.archive.org', 'ia801501.us.archive.org']:
    try:
        ips = socket.getaddrinfo(host, 443, socket.AF_INET)
        ip = ips[0][4][0]
        t0 = time.time()
        sock = socket.create_connection((ip, 443), timeout=8)
        elapsed = time.time() - t0
        print(f"   {host:35s} -> {ip:15s} OK  {elapsed:.2f}s")
        sock.close()
    except Exception as e:
        print(f"   {host:35s} ERRO {str(e)[:60]}")

# 5. Testar se o problema e so na porta 443/80 ou em todas as portas
print("\n5. Testar portas alternativas")
for port in [80, 443, 8080, 8443, 53]:
    try:
        t0 = time.time()
        sock = socket.create_connection(('archive.org', port), timeout=5)
        elapsed = time.time() - t0
        print(f"   porta {port:5d}: OK  {elapsed:.2f}s")
        sock.close()
    except Exception as e:
        print(f"   porta {port:5d}: ERRO {str(e)[:40]}")

# 6. Verificar se o IP responde em alguma porta
print("\n6. Scan rapido de portas no IP 207.241.224.2")
for port in [21, 22, 25, 53, 80, 443, 8080, 8443, 993, 995]:
    try:
        sock = socket.create_connection(('207.241.224.2', port), timeout=3)
        print(f"   porta {port:5d}: ABERTA")
        sock.close()
    except:
        pass  # Porta fechada/timeout - nao imprimir para nao poluir

# 7. Testar se o archive.org tem CDN ou mirror acessivel
print("\n7. Testar mirrors/CDN do archive.org")
# Archive.org usa ia###.us.archive.org para downloads
for host in ['ia801503.us.archive.org', 'ia902204.us.archive.org', 'ia801501.us.archive.org', 'ia801504.us.archive.org']:
    try:
        t0 = time.time()
        r = requests.get(f'https://{host}/', timeout=8, verify=False)
        elapsed = time.time() - t0
        print(f"   {host}: {r.status_code} em {elapsed:.2f}s")
    except Exception as e:
        print(f"   {host}: ERRO {str(e)[:60]}")

# 8. Verificar se o problema e DNS poisoning
print("\n8. Verificar IP real do archive.org (DNS publico)")
try:
    result = subprocess.run(['nslookup', 'archive.org', '8.8.8.8'], capture_output=True, text=True, timeout=10)
    print(f"   {result.stdout.strip()}")
except Exception as e:
    print(f"   ERRO: {e}")

# 9. Testar com Host header e IP diferente
print("\n9. Testar com Cloudflare DNS resolution (1.1.1.1)")
try:
    result = subprocess.run(['nslookup', 'archive.org', '1.1.1.1'], capture_output=True, text=True, timeout=10)
    print(f"   {result.stdout.strip()}")
except Exception as e:
    print(f"   ERRO: {e}")
