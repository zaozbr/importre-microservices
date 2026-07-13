const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const Logger = require('../../shared/logger');
const log = new Logger('aria2');

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

function aria2Download(url, outputPath, options = {}) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(ARIA2C)) return reject(new Error('aria2c.exe nao encontrado'));
    const connections = options.connections || 16;
    const split = options.split || 16;
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
      '--summary-interval=1'
    ];
    if (options.header) args.push('--header=' + options.header);
    const proc = spawn(ARIA2C, args, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = '';
    let stdout = '';
    function handleOutput(chunk) {
      const lastLine = chunk.trim().split('\n').pop();
      const speed = parseSpeed(lastLine);
      const pct = parseProgress(lastLine);
      if (options.onProgress && (speed || pct !== null)) {
        options.onProgress({ percent: pct || 0, speed });
      }
    }
    proc.stderr.on('data', d => { stderr += d.toString(); handleOutput(d.toString()); });
    proc.stdout.on('data', d => { stdout += d.toString(); handleOutput(d.toString()); });
    proc.on('exit', (code) => {
      if (code === 0 && fs.existsSync(outputPath)) resolve(outputPath);
      else reject(new Error(stderr.slice(0, 300) || `aria2 exit ${code}`));
    });
  });
}

module.exports = { aria2Download };
