// Proxy Tor SOCKS5 exclusivo para archive.org (contorna bloqueio do Avast Web Shield)
// Tor roda em localhost:9050 (SOCKS5)
// Bridge HTTP->SOCKS5 roda em localhost:8118 (para aria2 e axios)
// Nao afeta outros sites - apenas archive.org

const net = require('net');

let torEnabled = null;
let bridgeEnabled = null;
let httpsAgent = null;

function isTorRunning() {
  if (torEnabled !== null) return torEnabled;
  try {
    const sock = new net.Socket();
    sock.setTimeout(500);
    sock.connect(9050, '127.0.0.1');
    sock.on('connect', () => { torEnabled = true; sock.destroy(); });
    sock.on('error', () => { torEnabled = false; sock.destroy(); });
    sock.on('timeout', () => { torEnabled = false; sock.destroy(); });
  } catch { torEnabled = false; }
  return torEnabled !== false;
}

function isBridgeRunning() {
  if (bridgeEnabled !== null) return bridgeEnabled;
  try {
    const sock = new net.Socket();
    sock.setTimeout(500);
    sock.connect(8118, '127.0.0.1');
    sock.on('connect', () => { bridgeEnabled = true; sock.destroy(); });
    sock.on('error', () => { bridgeEnabled = false; sock.destroy(); });
    sock.on('timeout', () => { bridgeEnabled = false; sock.destroy(); });
  } catch { bridgeEnabled = false; }
  return bridgeEnabled !== false;
}

function getHttpsAgent() {
  if (!httpsAgent) {
    // https-proxy-agent v5 (compativel com Node.js 14+)
    const HttpsProxyAgent = require('https-proxy-agent');
    httpsAgent = new HttpsProxyAgent('http://127.0.0.1:8118');
  }
  return httpsAgent;
}

// Retorna config axios com proxy HTTP (bridge) se a URL for archive.org e o bridge estiver rodando
function getAxiosProxyConfig(url) {
  if (url && url.includes('archive.org') && isBridgeRunning()) {
    return { httpsAgent: getHttpsAgent(), httpAgent: getHttpsAgent(), proxy: false };
  }
  return {};
}

module.exports = { isTorRunning, isBridgeRunning, getAxiosProxyConfig };
