"""Diagnostico profundo do problema com archive.org."""
import socket, ssl, time, requests
from urllib.parse import urlparse

print("=== DIAGNOSTICO ARCHIVE.ORG ===\n")

# 1. DNS
print("1. DNS")
try:
    ips = socket.getaddrinfo('archive.org', 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
    for family, socktype, proto, canon, sockaddr in ips:
        family_name = 'IPv4' if family == socket.AF_INET else 'IPv6'
        print(f"   {family_name}: {sockaddr[0]}")
except Exception as e:
    print(f"   ERRO DNS: {e}")

# 2. Conexao TCP bruta na porta 443
print("\n2. Conexao TCP porta 443 (IPv4)")
try:
    t0 = time.time()
    sock = socket.create_connection(('archive.org', 443), timeout=10)
    elapsed = time.time() - t0
    print(f"   OK: conectado em {elapsed:.2f}s")
    sock.close()
except Exception as e:
    print(f"   ERRO: {e}")

# 3. Conexao TCP na porta 80 (HTTP)
print("\n3. Conexao TCP porta 80 (HTTP)")
try:
    t0 = time.time()
    sock = socket.create_connection(('archive.org', 80), timeout=10)
    elapsed = time.time() - t0
    print(f"   OK: conectado em {elapsed:.2f}s")
    sock.close()
except Exception as e:
    print(f"   ERRO: {e}")

# 4. SSL handshake
print("\n4. SSL handshake na porta 443")
try:
    ctx = ssl.create_default_context()
    t0 = time.time()
    sock = socket.create_connection(('archive.org', 443), timeout=10)
    ssock = ctx.wrap_socket(sock, server_hostname='archive.org')
    elapsed = time.time() - t0
    cert = ssock.getpeercert()
    print(f"   OK: SSL em {elapsed:.2f}s")
    print(f"   Cert subject: {cert.get('subject', '?')}")
    ssock.close()
except Exception as e:
    print(f"   ERRO SSL: {e}")

# 5. HTTP basico (porta 80)
print("\n5. HTTP GET na porta 80")
try:
    t0 = time.time()
    r = requests.get('http://archive.org/advancedsearch.php?q=test&output=json', 
                     timeout=10, allow_redirects=True)
    elapsed = time.time() - t0
    print(f"   Status: {r.status_code} em {elapsed:.2f}s, {len(r.text)} bytes")
    print(f"   URL final: {r.url[:80]}")
except Exception as e:
    print(f"   ERRO: {e}")

# 6. HTTPS com timeout maior
print("\n6. HTTPS GET com timeout 30s")
try:
    t0 = time.time()
    r = requests.get('https://archive.org/advancedsearch.php?q=test&output=json', 
                     timeout=30, allow_redirects=True)
    elapsed = time.time() - t0
    print(f"   Status: {r.status_code} em {elapsed:.2f}s, {len(r.text)} bytes")
except Exception as e:
    print(f"   ERRO: {str(e)[:150]}")

# 7. HTTPS com IP direto (bypass DNS)
print("\n7. HTTPS com IP direto (207.241.224.2)")
try:
    t0 = time.time()
    r = requests.get('https://207.241.224.2/advancedsearch.php?q=test&output=json', 
                     timeout=15, verify=False, headers={'Host': 'archive.org'})
    elapsed = time.time() - t0
    print(f"   Status: {r.status_code} em {elapsed:.2f}s")
except Exception as e:
    print(f"   ERRO: {str(e)[:150]}")

# 8. Testar se o problema e IPv6
print("\n8. Forcar IPv4")
try:
    import urllib3
    # Forcar IPv4 desabilitando IPv6
    socket.AF_INET6 = socket.AF_INET  # Hack: fazer IPv6 apontar para IPv4
    
    t0 = time.time()
    r = requests.get('https://archive.org/advancedsearch.php?q=test&output=json', 
                     timeout=15)
    elapsed = time.time() - t0
    print(f"   Status: {r.status_code} em {elapsed:.2f}s")
except Exception as e:
    print(f"   ERRO: {str(e)[:150]}")

# 9. Testar com curl
print("\n9. curl HTTPS")
import subprocess
try:
    result = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code} %{time_total}s', 
                            '--max-time', '15', 'https://archive.org/advancedsearch.php?q=test&output=json'],
                           capture_output=True, text=True, timeout=20)
    print(f"   curl: {result.stdout.strip()}")
    if result.stderr:
        print(f"   stderr: {result.stderr[:200]}")
except Exception as e:
    print(f"   ERRO: {e}")

# 10. traceroute parcial (primeiros saltos)
print("\n10. Primeiros saltos (tracert -d -h 5)")
try:
    result = subprocess.run(['tracert', '-d', '-h', '5', 'archive.org'],
                           capture_output=True, text=True, timeout=30)
    for line in result.stdout.split('\n')[:10]:
        if line.strip():
            print(f"   {line.strip()}")
except Exception as e:
    print(f"   ERRO: {e}")
