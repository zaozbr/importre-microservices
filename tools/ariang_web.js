const http = require("http"), fs = require("fs"), path = require("path");
const { execSync } = require("child_process");

const dir = "C:\\AriaNg-Web";
const SYSTEM_JSON = "C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\system.json";
const ARIA2_DEFAULT_PORT = 6800;

function execSyncSafe(cmd, timeoutMs = 5000) {
  try { return execSync(cmd, { encoding: "utf8", timeout: timeoutMs, windowsHide: true }); }
  catch (e) { return e.stdout || ""; }
}

/** PIDs de todos os aria2c.exe rodando. */
function allAria2cPids() {
  const pids = new Set();
  const output = execSyncSafe('wmic process where "name=\'aria2c.exe\'" get ProcessId /value');
  for (const line of output.split("\n")) {
    const m = line.match(/ProcessId=(\d+)/);
    if (m) pids.add(m[1]);
  }
  return [...pids];
}

/** Portas em LISTENING pertencentes aos PIDs dados. */
function portsForPids(pids) {
  if (!pids.length) return [];
  const pidSet = new Set(pids);
  const ports = new Set();
  const output = execSyncSafe("netstat -ano");
  for (const line of output.split("\n")) {
    if (!line.includes("LISTENING")) continue;
    const m = line.match(/:(\d+)\s+\S+\s+\S+\s+(\d+)\s*$/);
    if (m && pidSet.has(m[2])) {
      ports.add(parseInt(m[1]));
    }
  }
  return [...ports];
}

/** Le rpc-listen-port do system.json do Motrix. */
function readConfiguredPort() {
  try {
    const cfg = JSON.parse(fs.readFileSync(SYSTEM_JSON, "utf8"));
    if (cfg["rpc-listen-port"]) return parseInt(cfg["rpc-listen-port"]);
  } catch { /* sem config */ }
  return null;
}

/**
 * Descobre a porta RPC do aria2c dinamicamente:
 * 1. netstat: PIDs de aria2c.exe -> portas em LISTENING
 * 2. system.json rpc-listen-port
 * 3. Fallback: 6800 (default historico)
 */
function discoverRpcPort() {
  const pids = allAria2cPids();
  if (pids.length) {
    const ports = portsForPids(pids);
    if (ports.length) return ports[0];
  }
  const cfgPort = readConfiguredPort();
  if (cfgPort) return cfgPort;
  return ARIA2_DEFAULT_PORT;
}

/** Proxy RPC: repassa requisicoes POST /jsonrpc-proxy para o aria2c.
 *  Isso elimina problemas de CORS — o AriaNg fala com a mesma origem (16801). */
function proxyRpc(req, res) {
  const port = discoverRpcPort();
  let body = "";
  req.on("data", chunk => { body += chunk; });
  req.on("end", () => {
    const proxyReq = http.request({
      hostname: "127.0.0.1",
      port,
      path: "/jsonrpc",
      method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) }
    }, proxyRes => {
      res.writeHead(proxyRes.statusCode, {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      });
      proxyRes.pipe(res);
    });
    proxyReq.on("error", e => {
      res.writeHead(502, { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" });
      res.end(JSON.stringify({ error: "proxy error: " + e.message }));
    });
    proxyReq.write(body);
    proxyReq.end();
  });
}

const MIME = {
  ".html": "text/html",
  ".js": "application/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".eot": "application/vnd.ms-fontobject",
  ".map": "application/json"
};

http.createServer((req, res) => {
  // CORS preflight
  if (req.method === "OPTIONS") {
    res.writeHead(200, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type"
    });
    res.end();
    return;
  }

  // Endpoint dinamico: descobre a porta RPC do aria2c via netstat
  if (req.url === "/rpc-port") {
    const port = discoverRpcPort();
    res.writeHead(200, { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" });
    res.end(JSON.stringify({ port }));
    return;
  }

  // Proxy RPC: POST /jsonrpc-proxy -> repassa para aria2c na porta descoberta
  // Elimina CORS — AriaNg fala com mesma origem (16801)
  if (req.url === "/jsonrpc-proxy" && req.method === "POST") {
    proxyRpc(req, res);
    return;
  }

  // Servir arquivos estaticos do AriaNg
  const urlPath = req.url === "/" ? "/index.html" : req.url.split("?")[0];
  const f = path.join(dir, urlPath);
  fs.readFile(f, (err, data) => {
    if (err) {
      res.writeHead(404, { "Access-Control-Allow-Origin": "*" });
      res.end("not found");
    } else {
      const ext = path.extname(f);
      const mime = MIME[ext] || "application/octet-stream";
      res.writeHead(200, { "Content-Type": mime, "Access-Control-Allow-Origin": "*" });
      res.end(data);
    }
  });
}).listen(16801, () => console.log("AriaNg web em http://127.0.0.1:16801 (com proxy RPC)"));
