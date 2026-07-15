/**
 * aria2.js - Wrapper de download que usa Motrix (RPC porta 16800) como primario
 * e spawn de aria2c.exe como fallback se RPC estiver indisponivel.
 *
 * Suporta: HTTP, HTTPS, magnet links, arquivos .torrent locais.
 */
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const rpc = require('./aria2_rpc');

const ARIA2C = path.join(__dirname, '..', '..', 'aria2c.exe');

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
  if (isArchiveOrg && !isMagnet && !isTorrent) {
    try {
      const { getArchiveHeaders } = require('../../shared/archive_auth');
      const hdrs = getArchiveHeaders();
      headers = { Referer: 'https://archive.org/', Accept: '*/*' };
      if (hdrs['Cookie']) headers['Cookie'] = hdrs['Cookie'];
    } catch { /* sem auth, prossegue */ }
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
    headers
  });
}

/**
 * Fallback: spawn de aria2c.exe (codigo original preservado).
 */
function spawnDownload(url, outputPath, options = {}) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(ARIA2C)) return reject(new Error('aria2c.exe nao encontrado'));
    const isArchiveOrg = url.includes('archive.org');
    const isCoolrom = url.includes('coolrom');
    const connections = options.connections || (isArchiveOrg ? 64 : isCoolrom ? 32 : 16);
    const split = options.split || (isArchiveOrg ? 64 : isCoolrom ? 32 : 16);
    const args = [
      url,
      '--dir=' + path.dirname(outputPath),
      '--out=' + path.basename(outputPath),
      '--max-connection-per-server=' + connections,
      '--split=' + split,
      '--min-split-size=1M',
      '--max-tries=5',
      '--retry-wait=5',
      '--timeout=60',
      '--connect-timeout=30',
      '--continue=true',
      '--auto-file-renaming=false',
      '--allow-overwrite=true',
      '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
      '--summary-interval=1',
      '--max-overall-download-limit=0',
      '--max-download-limit=0',
      '--min-tls-version=TLSv1.2',
      '--max-resume-failure-tries=5',
      '--file-allocation=none',
      '--console-log-level=warn'
    ];
    if (options.maxTime) args.push('--max-download-result=' + options.maxTime);
    if (options.header) args.push('--header=' + options.header);
    if (isArchiveOrg) {
      try {
        const { getArchiveHeaders } = require('../../shared/archive_auth');
        const hdrs = getArchiveHeaders();
        args.push('--header=Referer: https://archive.org/');
        args.push('--header=Accept: */*');
        if (hdrs['Cookie']) args.push('--header=Cookie: ' + hdrs['Cookie']);
      } catch { /* sem auth */ }
    }
    if (options.extraHeaders) {
      for (const [key, value] of Object.entries(options.extraHeaders)) {
        args.push(`--header=${key}: ${value}`);
      }
    }
    const proc = spawn(ARIA2C, args, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = '';
    let lastProgress = { percent: 0, speed: null, bytes: 0 };
    let stalledSince = 0;
    let slowSince = 0;
    const slowThresholdMs = options.slowThresholdMs || 60000;
    const stalledThresholdMs = options.stalledThresholdMs || 90000;
    const minSpeedMbps = options.minSpeedMbps || (isArchiveOrg ? 0.10 : 0.5);
    let speedCheckTimer = null;

    function handleOutput(chunk) {
      const lastLine = chunk.trim().split('\n').pop();
      const speed = parseSpeed(lastLine);
      const pct = parseProgress(lastLine);
      if (speed || pct !== null) {
        lastProgress = { percent: pct || lastProgress.percent, speed: speed || lastProgress.speed };
        if (options.onProgress) options.onProgress(lastProgress);
      }
    }
    proc.stderr.on('data', d => { stderr += d.toString(); handleOutput(d.toString()); });
    proc.stdout.on('data', d => { handleOutput(d.toString()); });

    speedCheckTimer = setInterval(() => {
      const mbps = speedToMbps(lastProgress.speed);
      if (mbps < minSpeedMbps) {
        if (!slowSince) slowSince = Date.now();
        else if (Date.now() - slowSince > slowThresholdMs) {
          clearInterval(speedCheckTimer);
          proc.kill('SIGTERM');
          reject(new Error(`download muito lento: ${lastProgress.speed || '0'} por ${slowThresholdMs/1000}s (min ${minSpeedMbps}MB/s)`));
        }
      } else { slowSince = 0; }
      if (lastProgress.speed === null && lastProgress.percent < 100) {
        if (!stalledSince) stalledSince = Date.now();
        else if (Date.now() - stalledSince > stalledThresholdMs) {
          clearInterval(speedCheckTimer);
          proc.kill('SIGTERM');
          reject(new Error(`download travado por ${stalledThresholdMs/1000}s`));
        }
      } else { stalledSince = 0; }
    }, 5000);

    proc.on('exit', (code) => {
      clearInterval(speedCheckTimer);
      if (code === 0 && fs.existsSync(outputPath)) resolve(outputPath);
      else reject(new Error(stderr.slice(0, 300) || `aria2 exit ${code}`));
    });
  });
}

module.exports = { aria2Download, parseSpeed, parseProgress, parseSize, speedToMbps };
