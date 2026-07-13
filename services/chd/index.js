const express = require('express');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { PSX_DIR, CHDMAN_PATH, CHD_TEMP_DIR, PORTS, WORKERS } = require('../../shared/config');
const Logger = require('../../shared/logger');

const log = new Logger('chd-service');
const app = express();
app.use(express.json());

let status = { ready: 0, converting: [], completed: 0, failed: 0 };
let running = false;

function extractSerial(name) {
  const m = name.match(/([A-Z]{2,4}[-]\d{3,5})/i);
  return m ? m[1].toUpperCase() : null;
}

function buildChdName(cuePath) {
  const stem = path.basename(cuePath, path.extname(cuePath));
  const serial = extractSerial(stem);
  let base = stem
    .replace(/\(Track \d+\)/gi, '')
    .replace(/\(Disc \d+\)/gi, '')
    .replace(/\(.*?\)/g, '')
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .trim();
  if (serial) base = `${base}-${serial}`;
  return base.slice(0, 180).replace(/[.\s]+$/, '') + '.chd';
}

function findJobs() {
  const jobs = [];
  for (const ext of ['.cue']) {
    for (const cue of fs.readdirSync(PSX_DIR)) {
      if (!cue.endsWith(ext)) continue;
      if (cue.toLowerCase().includes('nao-conversivel')) continue;
      const cuePath = path.join(PSX_DIR, cue);
      const chdName = buildChdName(cuePath);
      const chdPath = path.join(PSX_DIR, chdName);
      if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1024 * 1024) continue;
      jobs.push({ cuePath, chdPath, chdName });
    }
  }
  return jobs;
}

function convertOne(job) {
  return new Promise((resolve) => {
    const tmpDir = CHD_TEMP_DIR;
    if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });

    const cueContent = fs.readFileSync(job.cuePath, 'utf-8');
    const refs = [...cueContent.matchAll(/FILE\s+"([^"]+)"/g)].map(m => m[1]);
    const hasBins = refs.every(r => fs.existsSync(path.join(path.dirname(job.cuePath), r)));
    if (!hasBins) {
      log.warn(`BINs faltando para ${path.basename(job.cuePath)}`);
      status.failed++;
      return resolve();
    }

    log.info(`Convertendo ${job.chdName}`);
    status.converting.push(job.chdName);
    const proc = spawn(CHDMAN_PATH, ['createcd', '-i', job.cuePath, '-o', job.chdPath, '-f'], { cwd: PSX_DIR });
    let stderr = '';
    proc.stderr.on('data', d => stderr += d.toString());
    proc.on('exit', (code) => {
      status.converting = status.converting.filter(n => n !== job.chdName);
      const ok = fs.existsSync(job.chdPath) && fs.statSync(job.chdPath).size > 1024 * 1024;
      if (ok) {
        log.info(`OK ${job.chdName} (${Math.round(fs.statSync(job.chdPath).size / 1024)}KB)`);
        status.completed++;
      } else {
        log.error(`Falha ${job.chdName}: ${stderr.slice(0, 200)}`);
        status.failed++;
      }
      resolve();
    });
  });
}

async function loop() {
  running = true;
  while (running) {
    const jobs = findJobs();
    status.ready = jobs.length;
    if (jobs.length) {
      const workers = Math.min(WORKERS.CHD, jobs.length);
      await Promise.all(jobs.slice(0, workers).map(convertOne));
    }
    await new Promise(r => setTimeout(r, 10000));
  }
}

app.get('/status', (req, res) => res.json(status));

process.on('uncaughtException', (e) => log.error(`uncaught: ${e.message}`));
process.on('unhandledRejection', (e) => log.error(`rejection: ${e.message}`));

app.listen(PORTS.CHD, '127.0.0.1', () => {
  log.info(`CHD service em http://127.0.0.1:${PORTS.CHD}`);
  loop();
});
