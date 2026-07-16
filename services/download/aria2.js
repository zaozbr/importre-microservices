/**
 * aria2.js - Wrapper de download que usa Motrix (RPC porta 16800) como primario
 * e spawn de aria2c.exe como fallback se RPC estiver indisponivel.
 *
 * Suporta: HTTP, HTTPS, magnet links, arquivos .torrent locais.
 */
const rpc = require('./aria2_rpc');

function parseSpeed(line) {
  const m = line.match(/DL:(\d+\.?\d*[KMGT]?i?B)/);
  return m ? m[1] + '/s' : null;
}

function parseProgress(line) {
  const mFull = line.match(/\[#[a-f0-9]+\s+(\d+\.?\d*[KMGT]?i?B)\/(\d+\.?\d*[KMGT]?i?B)\((\d+)%\)/);
  if (mFull) return parseInt(mFull[3], 10);
  const mPct = line.match(/\((\d+)%\)/);
  if (mPct) return parseInt(mPct[1], 10);
  const m = line.match(/\[#[a-f0-9]+\s+(\d+\.?\d*[KMGT]?i?B)\/(\d+\.?\d*[KMGT]?i?B)/);
  if (m) {
    const downloaded = parseSize(m[1]);
    const total = parseSize(m[2]);
    if (total > 0) return Math.round((downloaded / total) * 100);
  }
  return null;
}

function parseSize(s) {
  const units = { B: 1, KB: 1024, MB: 1048576, GB: 1073741824, TB: 1099511627776 };
  const m = s.match(/([\d.]+)([KMGT]?i?B)/);
  if (!m) return 0;
  const val = parseFloat(m[1]);
  let unit = m[2].replace('i', '').toUpperCase();
  if (unit === 'B') unit = 'B';
  return Math.round(val * (units[unit] || 1));
}

function speedToMbps(speedStr) {
  if (!speedStr) return 0;
  const m = speedStr.match(/([\d.]+)([KMGT]?i?)B\/s/);
  if (!m) return 0;
  const val = parseFloat(m[1]);
  const unit = (m[2] || '').toLowerCase();
  if (unit.startsWith('k')) return val / 1024;
  if (unit.startsWith('m')) return val;
  if (unit.startsWith('g')) return val * 1024;
  return val / 1048576; // bytes
}

/**
 * Download via Motrix RPC (primario) ou spawn (fallback).
 * Interface mantida compativel com a versao anterior.
 *
 * @param {string|string[]} url - HTTP, magnet, path .torrent local, ou array de URLs (multi-source)
 * @param {string} outputPath - path completo do arquivo de saida
 * @param {object} options - { connections, split, minSpeedMbps, slowThresholdMs, stalledThresholdMs, onProgress, extraHeaders, maxTimeMs }
 * @returns {Promise<string>} outputPath
 */
async function aria2Download(url, outputPath, options = {}) {
  // RPC direto - sem isAlive check, sem spawn fallback
  // O daemon aria2c deve ser mantido vivo externamente (ariang_watchdog)
  // Se RPC falhar, o retry do download service cuida de tentar novamente
  return rpcDownload(url, outputPath, options);
}

/**
 * Download via Motrix RPC.
 * Suporta multi-source: passar array de URLs para baixar chunks de multiplas fontes em paralelo.
 */
// Constroi headers e proxy para archive.org (cookies + Tor)
function buildArchiveOrgHeaders(primaryUrl, isMagnet, isTorrent) {
  let headers = null;
  let proxy = null;
  if (isMagnet || isTorrent) return { headers, proxy };
  try {
    const { getArchiveHeaders } = require('../../shared/archive_auth');
    const hdrs = getArchiveHeaders();
    headers = { Referer: 'https://archive.org/', Accept: '*/*' };
    if (hdrs['Cookie']) headers['Cookie'] = hdrs['Cookie'];
  } catch { /* sem auth, prossegue */ }
  try {
    const { isTorRunning } = require('../../shared/tor_proxy');
    if (isTorRunning() && primaryUrl.startsWith('https://')) {
      proxy = 'http://127.0.0.1:8118';
    }
  } catch { /* Tor nao disponivel, prossegue sem proxy */ }
  return { headers, proxy };
}

async function rpcDownload(urlOrUrls, outputPath, options = {}) {
  const urls = Array.isArray(urlOrUrls) ? urlOrUrls : [urlOrUrls];
  const primaryUrl = urls[0];
  const isArchiveOrg = urls.some(u => u.includes('archive.org'));
  const isMagnet = primaryUrl.startsWith('magnet:');
  const isTorrent = primaryUrl.endsWith('.torrent') && !primaryUrl.startsWith('http');
  const minSpeedMbps = options.minSpeedMbps || (isArchiveOrg ? 0.10 : 0.05);

  // Headers e proxy para archive.org
  const { headers: archHeaders, proxy } = isArchiveOrg ? buildArchiveOrgHeaders(primaryUrl, isMagnet, isTorrent) : { headers: null, proxy: null };
  let headers = archHeaders;
  // Headers extras do resolver (vimm cookies, retrostic referer, etc)
  if (options.extraHeaders) {
    headers = headers || {};
    Object.assign(headers, options.extraHeaders);
  }

  // Para torrents/magnets: aumentar timeout (BT e mais lento) e selecionar apenas ROMs
  const isBt = isMagnet || isTorrent;
  const btOpts = buildBtOptions(isBt, isArchiveOrg);

  // Multi-source: passar array de URLs se houver mais de uma
  const urlArg = urls.length > 1 && !isBt ? urls : primaryUrl;
  return rpc.rpcDownload(urlArg, outputPath, {
    connections: options.connections || (isArchiveOrg ? 64 : 16),
    split: options.split || (isArchiveOrg ? 64 : 16),
    maxTimeMs: options.maxTimeMs || btOpts.maxTimeMs,
    minSpeedMbps,
    slowThresholdMs: options.slowThresholdMs || btOpts.slowThresholdMs,
    stalledThresholdMs: options.stalledThresholdMs || btOpts.stalledThresholdMs,
    onProgress: options.onProgress,
    headers,
    proxy,
    btSelectFile: btOpts.btSelectFile
  });
}

function buildBtOptions(isBt, _isArchiveOrg) {
  if (!isBt) return { maxTimeMs: 1800000, slowThresholdMs: 180000, stalledThresholdMs: 300000, btSelectFile: undefined };
  return {
    maxTimeMs: 3600000,      // 60min para BT
    slowThresholdMs: 300000,  // 5min para considerar lento
    stalledThresholdMs: 600000, // 10min para considerar parado
    btSelectFile: '1-999'     // Selecionar todos os arquivos por padrao
  };
}

module.exports = { aria2Download, parseSpeed, parseProgress, parseSize, speedToMbps };
