// Bridge HTTP proxy -> Tor SOCKS5
// Permite que aria2 (que so suporta HTTP proxy) use o Tor (SOCKS5)
// Roda em localhost:8118 e encaminha tudo para socks5://127.0.0.1:9050
const http = require('http');
const { SocksClient } = require('socks');

const HTTP_PORT = 8118;
const SOCKS_HOST = '127.0.0.1';
const SOCKS_PORT = 9050;

const server = http.createServer((req, res) => {
  // HTTP CONNECT method (para HTTPS)
  // Nao deveria chegar aqui - CONNECT e tratado abaixo
  res.writeHead(405);
  res.end('Method Not Allowed');
});

// Tratar CONNECT (HTTPS tunneling)
server.on('connect', (req, clientSocket, head) => {
  const [host, port] = req.url.split(':');
  const targetPort = parseInt(port) || 443;

  SocksClient.createConnection({
    proxy: { host: SOCKS_HOST, port: SOCKS_PORT, type: 5 },
    command: 'connect',
    destination: { host, port: targetPort }
  }).then(({ socket }) => {
    clientSocket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
    if (head && head.length) socket.write(head);
    // Pipe bidirecional
    clientSocket.pipe(socket);
    socket.pipe(clientSocket);
    socket.on('error', () => clientSocket.destroy());
    clientSocket.on('error', () => socket.destroy());
    socket.on('close', () => clientSocket.destroy());
    clientSocket.on('close', () => socket.destroy());
  }).catch(() => {
    clientSocket.write('HTTP/1.1 502 Bad Gateway\r\n\r\n');
    clientSocket.destroy();
  });
});

// Tratar HTTP requests (nao-HTTPS) - forward via SOCKS
server.on('request', (req, res) => {
  if (req.url.startsWith('http://')) {
    const url = new URL(req.url);
    const host = url.hostname;
    const port = url.port || 80;

    SocksClient.createConnection({
      proxy: { host: SOCKS_HOST, port: SOCKS_PORT, type: 5 },
      command: 'connect',
      destination: { host, port: parseInt(port) }
    }).then(({ socket }) => {
      // Enviar requisicao HTTP original
      const reqLine = `${req.method} ${url.pathname}${url.search} HTTP/1.1\r\nHost: ${host}\r\n`;
      const headers = Object.entries(req.headers).map(([k, v]) => `${k}: ${v}`).join('\r\n');
      socket.write(reqLine + headers + '\r\n\r\n');
      req.pipe(socket);
      socket.pipe(res);
      socket.on('error', () => res.destroy());
      res.on('error', () => socket.destroy());
    }).catch(err => {
      res.writeHead(502);
      res.end('Bad Gateway: ' + err.message);
    });
  }
});

server.listen(HTTP_PORT, '127.0.0.1', () => {
  console.log(`HTTP->SOCKS5 bridge rodando em http://127.0.0.1:${HTTP_PORT} -> socks5://${SOCKS_HOST}:${SOCKS_PORT}`);
});
