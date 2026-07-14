/**
 * Cliente JSON-RPC para o daemon aria2c do Motrix (porta 16800).
 * Substitui o spawn de processo por chamadas RPC persistentes.
 * Suporta HTTP, magnet links e arquivos .torrent locais.
 */
const axios = require('axios');

const RPC_URL = 'http://127.0.0.1:16800/jsonrpc';
const RPC_TIMEOUT = 15000;
const POLL_INTERVAL_MS = 3000;
const DEFAULT_MAX_TIME_MS = 600000; // 10min por download

let rpcId = 1;

async function rpc(method, params = []) {
  const r = await axios.post(RPC_URL, {
    jsonrpc: '2.0',
    method,
    id: String(rpcId++),
    params
  }, { timeout: RPC_TIMEOUT });
  if (r.data.error) throw new Error(`RPC error: ${r.data.error.message} (code ${r.data.error.code})`);
  return r.data.result;
}

/**
 * Verifica se o daemon aria2c do Motrix esta rodando.
 * @returns {Promise<boolean>}
 */
async function isAlive() {
  try {
    const r = await rpc('aria2.getVersion');
    return !!r.version;
  } catch { return false; }
}

/**
 * Adiciona um download (HTTP, magnet ou .torrent) via RPC.
 * @param {string} url - URL HTTP, magnet link ou path para .torrent local
 * @param {string} dir - Diretorio de destino
 * @param {string} filename - Nome do arquivo de saida (opcional para torrent)
 * @param {object} opts - Opcoes extras do aria2 (headers, connections, etc)
 * @returns {Promise<string>} gid do download
 */
async function addDownload(url, dir, filename, opts = {}) {
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
  if (opts.headers) {
    const headerArr = [];
    for (const [k, v] of Object.entries(opts.headers)) {
      headerArr.push(`${k}: ${v}`);
    }
    options.header = headerArr;
  }

  // magnet: ou .torrent local -> addTorrent
  // HTTP/HTTPS -> addUri
  if (url.startsWith('magnet:')) {
    // addTorrent aceita [torrentFile|magnet, uris[], options]
    return rpc('aria2.addTorrent', [url, [], options]);
  }
  if (url.endsWith('.torrent') && !url.startsWith('http')) {
    // .torrent local: ler como base64
    const fs = require('fs');
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

    let status;
    try { status = await tellStatus(gid); }
    catch (e) {
      logProgress(`RPC erro obtendo status gid=${gid}: ${e.message}. Retry em 5s...`);
      await sleep(5000);
      try { status = await tellStatus(gid); }
      catch (e2) { logProgress(`RPC retry falhou gid=${gid}: ${e2.message}. Abortando.`); throw new Error(`RPC indisponivel: ${e2.message}`); }
    }

    const result = handleStatus(status, gid, outputPath, isBt, options);
    if (result.done) return result.value;
    if (result.error) throw result.error;

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
  const fs = require('fs');
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
  const fs = require('fs');
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
  // Log silencioso - pode ser capturado por logger externo
  if (process.env.ARIA2_RPC_DEBUG) console.log(`[aria2_rpc] ${msg}`);
}

module.exports = {
  rpc,
  isAlive,
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
  RPC_URL
};
