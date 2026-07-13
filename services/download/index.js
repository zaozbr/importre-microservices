const express = require('express');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { PSX_DIR, PORTS, WORKERS } = require('../../shared/config');
const Logger = require('../../shared/logger');

const log = new Logger('download-service');
const app = express();
app.use(express.json());

const QUEUE_URL = `http://127.0.0.1:${PORTS.QUEUE}`;

let status = { active: 0, completed: 0, failed: 0 };

async function queueRequest(method, endpoint, body) {
  const res = await axios({ method, url: `${QUEUE_URL}${endpoint}`, data: body, timeout: 5000 });
  return res.data;
}

function extractWith7z(archivePath, destDir) {
  return new Promise((resolve, reject) => {
    const proc = spawn('7z', ['x', '-y', '-o' + destDir, archivePath], { cwd: destDir });
    let stderr = '';
    proc.stderr.on('data', d => stderr += d.toString());
    proc.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr.slice(0, 200)));
    });
  });
}

async function downloadFile(item, url) {
  const ext = path.extname(new URL(url).pathname) || '.7z';
  const tmpPath = path.join(PSX_DIR, `${item.serial}${ext}`);
  const writer = fs.createWriteStream(tmpPath);
  const response = await axios({
    method: 'get',
    url,
    responseType: 'stream',
    timeout: 600000,
    maxRedirects: 5
  });
  response.data.pipe(writer);
  await new Promise((resolve, reject) => {
    writer.on('finish', resolve);
    writer.on('error', reject);
  });
  return tmpPath;
}

async function processOne() {
  const { item } = await queueRequest('post', '/queue/next-ready');
  if (!item) return false;

  const source = item.sources?.[0];
  if (!source || !source.url) {
    await queueRequest('post', '/queue/fail', { serial: item.serial, reason: 'sem URL' });
    return true;
  }

  status.active++;
  try {
    log.info(`Download ${item.serial} de ${source.url}`);
    const tmpPath = await downloadFile(item, source.url);
    if (tmpPath.endsWith('.7z') || tmpPath.endsWith('.zip') || tmpPath.endsWith('.rar')) {
      await extractWith7z(tmpPath, PSX_DIR);
      fs.unlinkSync(tmpPath);
    }
    await queueRequest('post', '/queue/complete', { serial: item.serial });
    status.completed++;
  } catch (e) {
    log.error(`Download falhou ${item.serial}: ${e.message}`);
    await queueRequest('post', '/queue/fail', { serial: item.serial, reason: e.message });
    status.failed++;
  }
  status.active--;
  return true;
}

async function loop() {
  while (true) {
    const workers = Array(WORKERS.DOWNLOAD).fill(null).map(async () => {
      while (await processOne()) {}
    });
    await Promise.all(workers);
    await new Promise(r => setTimeout(r, 10000));
  }
}

app.get('/status', (req, res) => res.json(status));

app.listen(PORTS.DOWNLOAD, () => {
  log.info(`Download service em http://127.0.0.1:${PORTS.DOWNLOAD}`);
  loop();
});
