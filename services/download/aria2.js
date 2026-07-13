const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const ARIA2C = path.join(__dirname, '..', '..', 'aria2c.exe');

function aria2Download(url, outputPath, options = {}) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(ARIA2C)) return reject(new Error('aria2c.exe nao encontrado'));
    const args = [
      url,
      '--dir=' + path.dirname(outputPath),
      '--out=' + path.basename(outputPath),
      '--max-connection-per-server=' + (options.connections || 16),
      '--split=' + (options.split || 16),
      '--min-split-size=1M',
      '--max-tries=5',
      '--retry-wait=5',
      '--timeout=60',
      '--connect-timeout=30',
      '--continue=true',
      '--auto-file-renaming=false',
      '--allow-overwrite=true',
      '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    ];
    if (options.header) args.push('--header=' + options.header);
    const proc = spawn(ARIA2C, args, { windowsHide: true });
    let stderr = '';
    proc.stderr.on('data', d => stderr += d.toString());
    proc.on('exit', (code) => {
      if (code === 0 && fs.existsSync(outputPath)) resolve(outputPath);
      else reject(new Error(stderr.slice(0, 300) || `aria2 exit ${code}`));
    });
  });
}

module.exports = { aria2Download };
