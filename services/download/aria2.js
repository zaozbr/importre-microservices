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
 * @param {string} url - HTTP, magnet ou path .torrent local
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
 */
async function rpcDownload(url, outputPath, options = {}) {
  const isArchiveOrg = url.includes('archive.org');
  const isMagnet = url.startsWith('magnet:');
  const isTorrent = url.endsWith('.torrent') && !url.startsWith('http');
  const minSpeedMbps = options.minSpeedMbps || (isArchiveOrg ? 0.10 : 0.05);

  // Headers para archive.org
  let headers = null;
  let proxy = null;
  if (isArchiveOrg && !isMagnet && !isTorrent) {
    try {
      const { getArchiveHeaders } = require('../../shared/archive_auth');
      const hdrs = getArchiveHeaders();
      headers = { Referer: 'https://archive.org/', Accept: '*/*' };
      if (hdrs['Cookie']) headers['Cookie'] = hdrs['Cookie'];
    } catch { /* sem auth, prossegue */ }
    // Proxy Tor (via bridge HTTP->SOCKS5) para contornar bloqueio do Avast Web Shield (apenas archive.org HTTPS)
    try {
      const { isTorRunning } = require('../../shared/tor_proxy');
      if (isTorRunning() && url.startsWith('https://')) {
        proxy = 'http://127.0.0.1:8118';
      }
    } catch { /* Tor nao disponivel, prossegue sem proxy */ }
  }
  // Headers extras do resolver (vimm cookies, retrostic referer, etc)
  if (options.extraHeaders) {
    headers = headers || {};
    Object.assign(headers, options.extraHeaders);
  }

  return rpc.rpcDownload(url, outputPath, {
    connections: options.connections || (isArchiveOrg ? 64 : 16),
    split: options.split || (isArchiveOrg ? 64 : 16),
    maxTimeMs: options.maxTimeMs || 1800000,
    minSpeedMbps,
    slowThresholdMs: options.slowThresholdMs || 180000,
    stalledThresholdMs: options.stalledThresholdMs || 300000,
    onProgress: options.onProgress,
    headers,
    proxy
  });
}

module.exports = { aria2Download, parseSpeed, parseProgress, parseSize, speedToMbps };
