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
    const m = line.match(/:\d+\s+\S+\s+\S+\s+(\d+)\s*$/);
    if (m && pidSet.has(m[1])) {
      const portMatch = line.match(/:(\d+)\s/);
      if (portMatch) ports.add(parseInt(portMatch[1]));
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
  // 1. netstat
  const pids = allAria2cPids();
  if (pids.length) {
    const ports = portsForPids(pids);
    if (ports.length) return ports[0]; // primeira porta em LISTENING do aria2c
  }
  // 2. system.json
  const cfgPort = readConfiguredPort();
  if (cfgPort) return cfgPort;
  // 3. fallback
  return ARIA2_DEFAULT_PORT;
}

http.createServer((req, res) => {
  // Endpoint dinamico: descobre a porta RPC do aria2c via netstat
  if (req.url === "/rpc-port") {
    const port = discoverRpcPort();
    res.writeHead(200, { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" });
    res.end(JSON.stringify({ port }));
    return;
  }
  const f = path.join(dir, req.url === "/" ? "index.html" : req.url);
  fs.readFile(f, (err, data) => {
    if (err) { res.writeHead(404); res.end("not found"); }
    else { res.writeHead(200, { "Content-Type": "text/html", "Access-Control-Allow-Origin": "*" }); res.end(data); }
  });
}).listen(16801, () => console.log("AriaNg web em http://127.0.0.1:16801"));
