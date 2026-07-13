"""
Proxy HTTP-to-SOCKS5 com Tor Stream Isolation.

Cada conexão HTTP através deste proxy usa um circuito Tor diferente,
fazendo com que archive.org veja IPs diferentes para cada download.
Isso contorna o rate limit de ~0.2MB/s por IP do archive.org.

Como funciona:
1. aria2c envia request HTTP CONNECT para este proxy (porta 8118)
2. Proxy abre conexão SOCKS5 para Tor (porta 9050)
3. Tor cria circuito único para cada conexão (stream isolation automático)
4. archive.org vê IP de saída diferente para cada download

Uso:
  python _tor_http_proxy.py          # inicia proxy na porta 8118
  python _tor_http_proxy.py --port 8118

Configurar aria2c:
  --all-proxy=http://127.0.0.1:8118
"""
import socket
import select
import threading
import struct
import sys
import os
import time
import argparse
from datetime import datetime

# Configuração
TOR_HOST = "127.0.0.1"
TOR_PORT = 9050
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8118

# Estatísticas
_stats_lock = threading.Lock()
_stats = {
    "connections": 0,
    "active": 0,
    "bytes_proxied": 0,
    "errors": 0,
    "started_at": time.time(),
}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def socks5_connect(dest_host, dest_port):
    """Conecta ao destino via Tor SOCKS5 com stream isolation.
    
    Usa SOCKS5 com autenticação de usuário única por conexão para forçar
    stream isolation (cada conexão usa circuito Tor diferente).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    
    try:
        # Conectar ao Tor
        sock.connect((TOR_HOST, TOR_PORT))
        
        # SOCKS5 greeting — usar autenticação de usuário/senha (0x02)
        # para forçar stream isolation (cada par user/passwd = circuito diferente)
        # Também oferecer "no auth" (0x00) como fallback
        sock.sendall(b"\x05\x02\x00\x02")  # versão 5, 2 métodos: no-auth, user/pass
        
        resp = sock.recv(2)
        if len(resp) < 2:
            raise Exception("Tor não respondeu ao greeting SOCKS5")
        
        if resp[0] != 0x05:
            raise Exception(f"Versão SOCKS inválida: {resp[0]}")
        
        method = resp[1]
        
        if method == 0x02:
            # Autenticação user/passwd — usar ID único para stream isolation
            # Tor usa o par user:passwd para determinar o circuito
            # user diferente = circuito diferente
            unique_id = f"dl{threading.get_ident()}_{int(time.time()*1000)}"
            user = unique_id.encode()
            passwd = unique_id.encode()
            
            # Formato: 0x01 + len(user) + user + len(passwd) + passwd
            auth = b"\x01" + bytes([len(user)]) + user + bytes([len(passwd)]) + passwd
            sock.sendall(auth)
            
            resp = sock.recv(2)
            if len(resp) < 2 or resp[1] != 0x00:
                raise Exception("Autenticação SOCKS5 falhou")
        
        elif method == 0x00:
            # Sem autenticação (sem stream isolation explícito)
            pass
        else:
            raise Exception(f"Método SOCKS5 não suportado: {method}")
        
        # SOCKS5 CONNECT request
        # Formato: ver(1) + cmd(1) + rsv(1) + atyp(1) + addr + port(2)
        if isinstance(dest_host, str):
            dest_host_bytes = dest_host.encode()
        else:
            dest_host_bytes = dest_host
        
        # Verificar se é IP ou hostname
        try:
            socket.inet_aton(dest_host_bytes.decode())
            # É IP — usar atyp=0x01 (IPv4)
            addr = b"\x01" + socket.inet_aton(dest_host_bytes.decode())
        except (OSError, UnicodeDecodeError):
            # É hostname — usar atyp=0x03 (domain)
            addr = b"\x03" + bytes([len(dest_host_bytes)]) + dest_host_bytes
        
        request = b"\x05\x01\x00" + addr + struct.pack("!H", dest_port)
        sock.sendall(request)
        
        # Resposta
        resp = sock.recv(10)
        if len(resp) < 2:
            raise Exception("Tor não respondeu ao CONNECT")
        
        if resp[1] != 0x00:
            error_codes = {
                0x01: "falha geral",
                0x02: "conexão não permitida",
                0x03: "rede inalcançável",
                0x04: "host inalcançável",
                0x05: "conexão recusada",
                0x06: "TTL expirado",
                0x07: "comando não suportado",
                0x08: "tipo de endereço não suportado",
            }
            err = error_codes.get(resp[1], f"código {resp[1]}")
            raise Exception(f"SOCKS5 CONNECT falhou: {err}")
        
        return sock
    
    except Exception:
        sock.close()
        raise


def handle_connect(client_sock, target_host, target_port):
    """Trata request HTTP CONNECT (túnel)."""
    try:
        remote_sock = socks5_connect(target_host, target_port)
        
        # Responder ao cliente: 200 Connection established
        client_sock.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
        
        # Tunnel bidirecional
        tunnel(client_sock, remote_sock)
        
    except Exception as e:
        with _stats_lock:
            _stats["errors"] += 1
        try:
            client_sock.sendall(f"HTTP/1.1 502 Bad Gateway\r\n\r\n{e}".encode())
        except:
            pass
    finally:
        try:
            client_sock.close()
        except:
            pass


def tunnel(sock1, sock2):
    """Túnel bidirecional entre dois sockets."""
    with _stats_lock:
        _stats["active"] += 1
    
    socks = [sock1, sock2]
    total_bytes = 0
    
    try:
        while True:
            r, _, _ = select.select(socks, [], [], 60)
            if not r:
                break  # timeout
            
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                
                total_bytes += len(data)
                other = sock2 if s is sock1 else sock1
                try:
                    other.sendall(data)
                except:
                    return
    except:
        pass
    finally:
        with _stats_lock:
            _stats["active"] -= 1
            _stats["bytes_proxied"] += total_bytes
        try:
            sock1.close()
        except:
            pass
        try:
            sock2.close()
        except:
            pass


def handle_client(client_sock, client_addr):
    """Trata cada conexão do cliente."""
    with _stats_lock:
        _stats["connections"] += 1
    
    try:
        client_sock.settimeout(30)
        request = b""
        while b"\r\n\r\n" not in request and len(request) < 8192:
            chunk = client_sock.recv(4096)
            if not chunk:
                break
            request += chunk
        
        if not request:
            return
        
        # Parse da primeira linha
        first_line = request.split(b"\r\n")[0].decode("utf-8", errors="replace")
        parts = first_line.split()
        
        if len(parts) < 2:
            return
        
        method = parts[0]
        target = parts[1]
        
        if method == "CONNECT":
            # CONNECT host:port HTTP/1.1
            host_port = target.split(":")
            target_host = host_port[0]
            target_port = int(host_port[1]) if len(host_port) > 1 else 443
            handle_connect(client_sock, target_host, target_port)
        else:
            # Request HTTP normal (GET, POST, etc.)
            # Parse URL
            if target.startswith("http://"):
                target = target[7:]
            elif target.startswith("https://"):
                target = target[8:]
            
            # Separar host:port/path
            path_start = target.find("/")
            if path_start == -1:
                host_part = target
                path = "/"
            else:
                host_part = target[:path_start]
                path = target[path_start:]
            
            if ":" in host_part:
                target_host, target_port = host_part.split(":")
                target_port = int(target_port)
            else:
                target_host = host_part
                target_port = 80 if not first_line.startswith("CONNECT") else 443
            
            # Conectar via Tor
            try:
                remote_sock = socks5_connect(target_host, target_port)
                
                # Reescrever request com path relativo
                # Substituir primeira linha
                new_first_line = f"{method} {path} HTTP/1.1"
                request_lines = request.split(b"\r\n")
                request_lines[0] = new_first_line.encode()
                new_request = b"\r\n".join(request_lines)
                
                remote_sock.sendall(new_request)
                
                # Tunnel
                tunnel(client_sock, remote_sock)
                
            except Exception as e:
                with _stats_lock:
                    _stats["errors"] += 1
                try:
                    client_sock.sendall(f"HTTP/1.1 502 Bad Gateway\r\n\r\nTor error: {e}".encode())
                except:
                    pass
    
    except Exception as e:
        with _stats_lock:
            _stats["errors"] += 1
    finally:
        try:
            client_sock.close()
        except:
            pass


def stats_printer():
    """Imprime estatísticas a cada 30s."""
    while True:
        time.sleep(30)
        with _stats_lock:
            uptime = time.time() - _stats["started_at"]
            mb = _stats["bytes_proxied"] / 1024 / 1024
            print(f"[stats] uptime={uptime:.0f}s conns={_stats['connections']} "
                  f"active={_stats['active']} proxied={mb:.1f}MB "
                  f"errors={_stats['errors']}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PROXY_PORT)
    parser.add_argument("--host", type=str, default=PROXY_HOST)
    args = parser.parse_args()
    
    # Thread de stats
    t = threading.Thread(target=stats_printer, daemon=True)
    t.start()
    
    # Servidor
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(128)
    
    log(f"Proxy HTTP-to-SOCKS5 (Tor) escutando em {args.host}:{args.port}")
    log(f"Tor SOCKS5 em {TOR_HOST}:{TOR_PORT}")
    log(f"Stream isolation: habilitado (user/passwd único por conexão)")
    log(f"Configurar aria2c: --all-proxy=http://{args.host}:{args.port}")
    
    try:
        while True:
            client_sock, client_addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client_sock, client_addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        log("Encerrando...")
        server.close()


if __name__ == "__main__":
    main()
