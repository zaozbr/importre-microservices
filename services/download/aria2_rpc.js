/**
 * Cliente JSON-RPC para o daemon aria2c (porta dinamica via netstat).
 * Usa WebSocket como transporte primario (conexao unica persistente, 0 CLOSE_WAIT).
 * HTTP axios como fallback se WebSocket falhar.
 * Suporta HTTP, magnet links e arquivos .torrent locais.
 *
 * A porta RPC e descoberta dinamicamente:
 * 1. netstat: PIDs de aria2c.exe -> portas em LISTENING -> probe
 * 2. system.json do Motrix (rpc-listen-port)
 * 3. Variavel de ambiente ARIA2_RPC_PORT
 * 4. Fallback: 6800 (default historico)
 */
const axios = require('axios');
const WebSocket = require('ws');
const { execSync } = require('child_process');
const fs = require('fs');

const SYSTEM_JSON = 'C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\system.json';
const DEFAULT_PORT = 6800;
const RPC_TIMEOUT = 15000;
const POLL_INTERVAL_MS = 5000;
const DEFAULT_MAX_TIME_MS = 600000; // 10min por download

let rpcId = 1;

// === Descoberta dinamica de porta RPC ===
let discoveredPort = null;
let lastPortDiscovery = 0;
const PORT_DISCOVERY_TTL_MS = 30000; // redescobre a cada 30s se necessario

function execSyncSafe(cmd, timeoutMs = 5000) {
  try { return execSync(cmd, { encoding: 'utf8', timeout: timeoutMs, windowsHide: true }); }
  catch (e) { return e.stdout || ''; }
}

/** PIDs de todos os aria2c.exe rodando. */
function allAria2cPids() {
  const pids = new Set();
  const output = execSyncSafe('wmic process where "name=\'aria2c.exe\'" get ProcessId /value');
  for (const line of output.split('\n')) {
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
  const output = execSyncSafe('netstat -ano');
  for (const line of output.split('\n')) {
    if (!line.includes('LISTENING')) continue;
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
    const cfg = JSON.parse(fs.readFileSync(SYSTEM_JSON, 'utf8'));
    if (cfg['rpc-listen-port']) return parseInt(cfg['rpc-listen-port']);
  } catch { /* sem config */ }
  return null;
}

/** Probe async com axios. */
async function probePortAsync(port) {
  try {
    const r = await axios.post(`http://127.0.0.1:${port}/jsonrpc`, {
      jsonrpc: '2.0', method: 'aria2.getVersion', id: 'probe', params: []
    }, { timeout: 3000 });
    return !!(r.data.result && r.data.result.version);
  } catch { return false; }
}

/**
 * Descobre a porta RPC dinamicamente:
 * 1. Porta ja conhecida (se ainda valida)
 * 2. netstat: PIDs de aria2c.exe -> portas em LISTENING -> probe
 * 3. system.json rpc-listen-port
 * 4. Variavel de ambiente ARIA2_RPC_PORT
 * 5. Fallback: 6800
 */
async function discoverPort() {
  const now = Date.now();

  // 1. Porta ja conhecida e ainda valida (TTL)
  if (discoveredPort && (now - lastPortDiscovery) < PORT_DISCOVERY_TTL_MS) {
    return discoveredPort;
  }

  // 2. netstat: encontra portas que aria2c.exe esta ouvindo
  const pids = allAria2cPids();
  if (pids.length) {
    const ports = portsForPids(pids);
    for (const port of ports) {
      if (await probePortAsync(port)) {
        if (discoveredPort !== port) {
          logProgress(`Porta RPC descoberta via netstat: ${port}`);
        }
        discoveredPort = port;
        lastPortDiscovery = now;
        return port;
      }
    }
  }

  // 3. system.json do Motrix
  const cfgPort = readConfiguredPort();
  if (cfgPort && await probePortAsync(cfgPort)) {
    discoveredPort = cfgPort;
    lastPortDiscovery = now;
    return cfgPort;
  }

  // 4. Variavel de ambiente
  const envPort = parseInt(process.env.ARIA2_RPC_PORT);
  if (envPort && await probePortAsync(envPort)) {
    discoveredPort = envPort;
    lastPortDiscovery = now;
    return envPort;
  }

  // 5. Fallback: 6800
  if (await probePortAsync(DEFAULT_PORT)) {
    discoveredPort = DEFAULT_PORT;
    lastPortDiscovery = now;
    return DEFAULT_PORT;
  }

  // Nada encontrado — retornar ultima conhecida ou default
  return discoveredPort || DEFAULT_PORT;
}

/** Obtem a porta atual (descobre se necessario). */
async function getPort() {
  return discoverPort();
}

/** Forca redescoberta (chamar se a conexao cair). */
function invalidatePort() {
  discoveredPort = null;
  lastPortDiscovery = 0;
}

// === Cliente WebSocket RPC ===
// Mantem uma unica conexao persistente - elimina CLOSE_WAIT completamente
let ws = null;
let wsReady = false;
let wsEverConnected = false; // Track se WS ja conectou alguma vez
const wsCallbacks = new Map(); // id -> {resolve, reject, timeout}

async function connectWs() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  const port = await getPort();
  const wsUrl = `ws://127.0.0.1:${port}/jsonrpc`;
  try {
    ws = new WebSocket(wsUrl);
  } catch { ws = null; wsReady = false; return; }
  ws.on('open', () => { wsReady = true; wsEverConnected = true; });
  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data.toString());
      if (msg.id !== undefined && wsCallbacks.has(msg.id)) {
        const cb = wsCallbacks.get(msg.id);
        wsCallbacks.delete(msg.id);
        clearTimeout(cb.timeout);
        if (msg.error) cb.reject(new Error(`RPC error: ${msg.error.message}`));
        else cb.resolve(msg.result);
      }
    } catch { /* ignore parse errors */ }
  });
  ws.on('close', () => {
    wsReady = false;
    for (const [id, cb] of wsCallbacks) {
      clearTimeout(cb.timeout);
      cb.reject(new Error('WebSocket closed'));
      wsCallbacks.delete(id);
    }
    invalidatePort(); // forcar redescoberta na reconexao
    setTimeout(() => connectWs(), 3000);
  });
  ws.on('error', () => { wsReady = false; });
}

function wsRpc(method, params = []) {
  return new Promise((resolve, reject) => {
    if (!wsReady || !ws) {
      reject(new Error('WebSocket not ready'));
      return;
    }
    const id = String(rpcId++);
    const timeout = setTimeout(() => {
      wsCallbacks.delete(id);
      reject(new Error(`RPC timeout: ${method}`));
    }, RPC_TIMEOUT);
    wsCallbacks.set(id, { resolve, reject, timeout });
    ws.send(JSON.stringify({ jsonrpc: '2.0', method, id, params }));
  });
}

// Iniciar conexao WebSocket (async, nao bloqueia require)
connectWs().catch(() => {});

// HTTP axios como fallback
const http = require('http');
const httpAgent = new http.Agent({
  keepAlive: true,
  maxSockets: 32,
  maxFreeSockets: 4,
  timeout: 30000,
  keepAliveMsecs: 15000
});
const rpcAxios = axios.create({
  timeout: RPC_TIMEOUT,
  httpAgent,
  headers: { 'Connection': 'keep-alive' }
});

// === Monitor compartilhado ===
// Em vez de cada rpcDownload() chamar tellStatus(gid) individualmente,
// um unico monitor chama tellActive() + tellStopped() e cacheia resultados.
// Reduz chamadas RPC de N (uma por download) para 2 por ciclo.
const statusCache = new Map(); // gid -> status
let monitorRunning = false;

async function startMonitor() {
  if (monitorRunning) return;
  monitorRunning = true;
  while (true) {
    try {
      // 1. tellActive: todos os downloads ativos em uma chamada
      const active = await tellActive();
      const activeGids = new Set();
      for (const d of active) {
        statusCache.set(d.gid, d);
        activeGids.add(d.gid);
      }
      // 2. tellStopped: downloads completados/erro em uma chamada (nao individual)
      const stopped = await tellStopped(0, 50);
      for (const d of stopped) {
        if (d.status === 'complete' || d.status === 'error' || d.status === 'removed') {
          statusCache.set(d.gid, d);
        }
      }
      // 3. Limpar cache de gids que nao estao nem ativos nem parados
      for (const [gid, st] of statusCache) {
        if (!activeGids.has(gid) && st.status === 'active') {
          statusCache.delete(gid);
        }
      }
    } catch (e) {
      // Monitor erro - continua tentando
    }
    await sleep(POLL_INTERVAL_MS);
  }
}

function getCachedStatus(gid) {
  return statusCache.get(gid);
}

async function rpc(method, params = []) {
  // WebSocket apenas - sem HTTP fallback (HTTP causa CLOSE_WAIT no aria2c Windows)
  // Se WS ja conectou antes, esperar ate 5s para reconectar
  // Se WS nunca conectou (ex: testes), ir direto para HTTP fallback
  if (wsEverConnected) {
    for (let i = 0; i < 10; i++) {
      if (wsReady && ws && ws.readyState === WebSocket.OPEN) break;
      if (!ws || ws.readyState === WebSocket.CLOSED) { await connectWs(); }
      await new Promise(r => setTimeout(r, 500));
    }
  }
  if (wsReady && ws && ws.readyState === WebSocket.OPEN) {
    try {
      return await wsRpc(method, params);
    } catch (e) {
      if (!e.message.includes('timeout')) connectWs().catch(() => {});
    }
  }
  // Fallback HTTP (apenas se WS nao disponivel)
  const port = await getPort();
  const rpcUrl = `http://127.0.0.1:${port}/jsonrpc`;
  const r = await rpcAxios.post(rpcUrl, {
    jsonrpc: '2.0',
    method,
    id: String(rpcId++),
    params
  });
  if (r.data.error) throw new Error(`RPC error: ${r.data.error.message} (code ${r.data.error.code})`);
  return r.data.result;
}

/**
 * Multicall - agrupa multiplas chamadas RPC em uma so requisicao.
 * Reduz drasticamente o overhead no daemon aria2.
 */
async function multicall(calls) {
  const result = await rpc('system.multicall', [calls.map(c => ({ methodName: c.method, params: c.params }))]);
  return result.map(item => item[0] !== undefined ? item[0] : null);
}

/**
 * Verifica se o daemon aria2c esta rodando.
 * @returns {Promise<boolean>}
 */
async function isAlive() {
  try {
    const r = await rpc('aria2.getVersion');
    return !!r.version;
  } catch { return false; }
}

/**
 * Retorna a porta RPC atual em uso.
 * @returns {Promise<number>}
 */
async function getRpcPort() {
  return getPort();
}

/**
 * Adiciona um download (HTTP, magnet ou .torrent) via RPC.
 * @param {string} url - URL HTTP, magnet link ou path para .torrent local
 * @param {string} dir - Diretorio de destino
 * @param {string} filename - Nome do arquivo de saida (opcional para torrent)
 * @param {object} opts - Opcoes extras do aria2 (headers, connections, etc)
 * @returns {Promise<string>} gid do download
 */
/** Le cookies do archive.org e retorna como header string. */
function getArchiveCookieHeader() {
  try {
    const cookieFile = 'F:\\importre\\archive_cookies.txt';
    if (!fs.existsSync(cookieFile)) return null;
    const cookies = fs.readFileSync(cookieFile, 'utf8');
    const cookiePairs = [];
    for (const line of cookies.split('\n')) {
      if (line.startsWith('#') || !line.trim()) continue;
      const parts = line.split('\t');
      if (parts.length >= 7) cookiePairs.push(`${parts[5]}=${parts[6]}`);
    }
    return cookiePairs.length ? `Cookie: ${cookiePairs.join('; ')}` : null;
  } catch { return null; }
}

/** Constroi array de headers para o download. */
function buildHeaders(url, opts) {
  const headerArr = [];
  if (opts.headers) {
    for (const [k, v] of Object.entries(opts.headers)) {
      headerArr.push(`${k}: ${v}`);
    }
  }
  if (url.includes('archive.org')) {
    const cookieHeader = getArchiveCookieHeader();
    if (cookieHeader) headerArr.push(cookieHeader);
  }
  return headerArr;
}

/** Constroi options do aria2 para addDownload. */
function buildDownloadOptions(dir, filename, opts, headerArr) {
  const options = {
    dir,
    'max-connection-per-server': String(opts.connections || 16),
    split: String(opts.split || 16),
    'min-split-size': '1M',
    'continue': 'true',
    'file-allocation': 'none',
    'check-certificate': 'false',
    'max-tries': String(opts.maxTries || 5),
    'retry-wait': '5',
    'timeout': '60',
    'connect-timeout': '30',
    'seed-time': '0',
    ...opts.aria2Options
  };
  if (filename) options.out = filename;
  if (headerArr.length) options.header = headerArr;
  return options;
}

async function addDownload(url, dir, filename, opts = {}) {
  const headerArr = buildHeaders(url, opts);
  const options = buildDownloadOptions(dir, filename, opts, headerArr);

  // magnet: ou .torrent local -> addTorrent
  // HTTP/HTTPS -> addUri
  if (url.startsWith('magnet:')) {
    return rpc('aria2.addTorrent', [url, [], options]);
  }
  if (url.endsWith('.torrent') && !url.startsWith('http')) {
    const torrentData = fs.readFileSync(url);
    return rpc('aria2.addTorrent', [torrentData.toString('base64'), [], options]);
  }
  // HTTP/HTTPS
  return rpc('aria2.addUri', [[url], options]);
}

/**
 * Obtem status de um download por gid.
 * @param {string} gid
 * @returns {Promise<object>} status object
 */
async function tellStatus(gid) {
  return rpc('aria2.tellStatus', [gid]);
}

/**
 * Remove um download (cancela se ativo).
 * @param {string} gid
 */
async function removeDownload(gid) {
  try {
    await rpc('aria2.forceRemove', [gid]);
  } catch { /* ja removido */ }
}

/**
 * Remove resultado de download parado.
 * @param {string} gid
 */
async function removeDownloadResult(gid) {
  try {
    await rpc('aria2.removeDownloadResult', [gid]);
  } catch { /* ja limpo */ }
}

/**
 * Lista todos os downloads ativos.
 * @returns {Promise<array>}
 */
async function tellActive() {
  return rpc('aria2.tellActive', []);
}

/**
 * Lista downloads parados (completados/erro).
 * @param {number} offset
 * @param {number} num
 * @returns {Promise<array>}
 */
async function tellStopped(offset = 0, num = 100) {
  return rpc('aria2.tellStopped', [offset, num]);
}

/**
 * Lista downloads em espera.
 * @param {number} offset
 * @param {number} num
 * @returns {Promise<array>}
 */
async function tellWaiting(offset = 0, num = 100) {
  return rpc('aria2.tellWaiting', [offset, num]);
}

/**
 * Estatisticas globais.
 * @returns {Promise<object>}
 */
async function getGlobalStat() {
  return rpc('aria2.getGlobalStat', []);
}

/**
 * Muda opcoes globais.
 * @param {object} options
 */
async function changeGlobalOption(options) {
  return rpc('aria2.changeGlobalOption', [options]);
}

/**
 * Limpa todos os resultados de downloads parados.
 */
async function purgeDownloadResult() {
  return rpc('aria2.purgeDownloadResult', []);
}

/**
 * Baixa um arquivo via RPC e aguarda conclusao.
 * Substitui aria2Download() do aria2.js.
 *
 * @param {string} url - URL HTTP, magnet ou .torrent
 * @param {string} outputPath - Path completo do arquivo de saida
 * @param {object} options - { connections, split, maxTimeMs, onProgress, headers, minSpeedMbps, slowThresholdMs, stalledThresholdMs }
 * @returns {Promise<string>} outputPath se sucesso
 */
async function rpcDownload(url, outputPath, options = {}) {
  const path = require('path');
  const dir = path.dirname(outputPath);
  const filename = path.basename(outputPath);
  const maxTimeMs = options.maxTimeMs || DEFAULT_MAX_TIME_MS;
  const isMagnet = url.startsWith('magnet:');
  const isTorrent = url.endsWith('.torrent') && !url.startsWith('http');
  const isBt = isMagnet || isTorrent;

  const addOpts = buildAddOpts(options, isBt);
  const gid = await addDownload(url, dir, isBt ? null : filename, addOpts);
  logProgress(`RPC download iniciado: gid=${gid} url=${url.substring(0, 80)}...`);

  // Iniciar monitor compartilhado se ainda nao estiver rodando
  startMonitor().catch(() => {});

  const ctx = {
    startTime: Date.now(),
    lastCompleted: 0,
    lastCheckTime: Date.now(),
    slowSince: 0,
    stalledSince: 0,
    slowThresholdMs: options.slowThresholdMs || 60000,
    stalledThresholdMs: options.stalledThresholdMs || 90000,
    minSpeedBps: (options.minSpeedMbps || 0.25) * 1048576,
    maxTimeMs
  };

  while (true) {
    await sleep(POLL_INTERVAL_MS);
    if (checkTimeout(ctx)) {
      await removeDownload(gid);
      throw new Error(`timeout ${ctx.maxTimeMs / 1000}s excedido para ${url.substring(0, 60)}`);
    }

    // Ler status do cache compartilhado (sem chamada RPC individual)
    let status = getCachedStatus(gid);
    if (!status) {
      try { status = await tellStatus(gid); }
      catch (e) {
        logProgress(`RPC erro obtendo status gid=${gid}: ${e.message}. Retry...`);
        await sleep(5000);
        try { status = await tellStatus(gid); }
        catch (e2) { logProgress(`RPC retry falhou gid=${gid}: ${e2.message}. Abortando.`); throw new Error(`RPC indisponivel: ${e2.message}`); }
      }
    }

    const result = handleStatus(status, gid, outputPath, isBt, options);
    if (result.done) {
      statusCache.delete(gid);
      return result.value;
    }
    if (result.error) {
      statusCache.delete(gid);
      throw result.error;
    }

    updateProgressTracking(ctx, status, options);
  }
}

function buildAddOpts(options, isBt) {
  const addOpts = {
    connections: options.connections || 16,
    split: options.split || 16,
    maxTries: 0,
    aria2Options: {}
  };
  if (!isBt) {
    addOpts.headers = options.headers || null;
    // Proxy SOCKS5 para contornar bloqueio do Avast (apenas archive.org HTTPS)
    if (options.proxy) {
      addOpts.aria2Options['all-proxy'] = options.proxy;
    }
  } else {
    addOpts.aria2Options['seed-time'] = '0';
    addOpts.aria2Options['bt-metadata-only'] = 'false';
    addOpts.aria2Options['bt-remove-unselected-file'] = 'true';
  }
  return addOpts;
}

function checkTimeout(ctx) {
  return (Date.now() - ctx.startTime) > ctx.maxTimeMs;
}

function handleStatus(status, gid, outputPath, isBt, _options) {
  if (status.status === 'complete') {
    if (isBt) return { done: true, value: resolveBtFile(status, outputPath) };
    if (fs.existsSync(outputPath)) return { done: true, value: outputPath };
    return { done: true, error: new Error('download completo mas arquivo nao encontrado') };
  }
  if (status.status === 'error') {
    removeDownloadResult(gid).catch(() => {});
    return { done: true, error: new Error(`aria2 erro: ${status.errorMessage || 'desconhecido'}`) };
  }
  if (status.status === 'removed') {
    return { done: true, error: new Error('download removido') };
  }
  return { done: false };
}

function resolveBtFile(status, outputPath) {
  const files = status.files || [];
  const downloaded = files.find(f => f.completedLength === f.length && f.length > 0);
  if (downloaded && fs.existsSync(downloaded.path)) {
    if (downloaded.path !== outputPath) {
      try {
        if (fs.existsSync(outputPath)) fs.unlinkSync(outputPath);
        fs.renameSync(downloaded.path, outputPath);
      } catch { return downloaded.path; }
    }
    return outputPath;
  }
  return outputPath;
}

function updateProgressTracking(ctx, status, options) {
  const completed = parseInt(status.completedLength) || 0;
  const total = parseInt(status.totalLength) || 0;
  const speed = parseInt(status.downloadSpeed) || 0;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

  if (options.onProgress) {
    options.onProgress({ percent, speed: formatSpeed(speed), bytes: completed });
  }

  const now = Date.now();
  const checkElapsed = (now - ctx.lastCheckTime) / 1000;
  if (checkElapsed > 0) {
    const bytesPerSec = (completed - ctx.lastCompleted) / checkElapsed;
    if (bytesPerSec < ctx.minSpeedBps && completed < total) {
      if (!ctx.slowSince) ctx.slowSince = now;
      else if (now - ctx.slowSince > ctx.slowThresholdMs) {
        removeDownload(status.gid).catch(() => {});
        throw new Error(`download lento: ${formatSpeed(speed)} por ${ctx.slowThresholdMs / 1000}s`);
      }
    } else { ctx.slowSince = 0; }
  }
  if (speed === 0 && completed < total) {
    if (!ctx.stalledSince) ctx.stalledSince = now;
    else if (now - ctx.stalledSince > ctx.stalledThresholdMs) {
      removeDownload(status.gid).catch(() => {});
      throw new Error(`download travado por ${ctx.stalledThresholdMs / 1000}s`);
    }
  } else { ctx.stalledSince = 0; }

  ctx.lastCompleted = completed;
  ctx.lastCheckTime = now;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function formatSpeed(bps) {
  if (bps >= 1048576) return (bps / 1048576).toFixed(1) + 'MiB/s';
  if (bps >= 1024) return (bps / 1024).toFixed(1) + 'KiB/s';
  return bps + 'B/s';
}

function logProgress(msg) {
  if (process.env.ARIA2_RPC_DEBUG) console.log(`[aria2_rpc] ${msg}`);
}

module.exports = {
  rpc,
  multicall,
  isAlive,
  getRpcPort,
  addDownload,
  tellStatus,
  removeDownload,
  removeDownloadResult,
  tellActive,
  tellStopped,
  tellWaiting,
  getGlobalStat,
  changeGlobalOption,
  purgeDownloadResult,
  rpcDownload,
  startMonitor,
  getCachedStatus,
  invalidatePort
};
