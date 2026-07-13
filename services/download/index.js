const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { PSX_DIR, PORTS, WORKERS } = require('../../shared/config');
const Logger = require('../../shared/logger');
const { aria2Download } = require('./aria2');

const log = new Logger('download-service');
const app = express();
app.use(express.json());
app.use('/shared', express.static(path.join(__dirname, '..', '..', 'shared')));

const QUEUE_URL = `http://127.0.0.1:${PORTS.QUEUE}`;

let status = { active: 0, completed: 0, failed: 0 };

async function queueRequest(method, endpoint, body) {
  const res = await axios({ method, url: `${QUEUE_URL}${endpoint}`, data: body, timeout: 5000 });
  return res.data;
}

async function resolveCoolrom(pageUrl) {
  const res = await axios.get(pageUrl, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
    timeout: 20000
  });
  const $ = cheerio.load(res.data);
  const link = $('a[href*="dl.coolrom"]').attr('href');
  if (!link) throw new Error('link coolrom nao encontrado');
  return link;
}

function extractWith7z(archivePath, destDir) {
  return new Promise((resolve, reject) => {
    const sevenZip = process.env.SEVEN_ZIP_PATH || 'C:\\Program Files\\7-Zip\\7z.exe';
    const proc = spawn(sevenZip, ['x', '-y', '-o' + destDir, archivePath], { cwd: destDir });
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
  try {
    await aria2Download(url, tmpPath, { connections: 16, split: 16 });
  } catch (e) {
    // fallback axios
    const writer = fs.createWriteStream(tmpPath);
    const response = await axios({
      method: 'get',
      url,
      responseType: 'stream',
      timeout: 600000,
      maxRedirects: 5,
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }
    });
    response.data.pipe(writer);
    await new Promise((resolve, reject) => {
      writer.on('finish', resolve);
      writer.on('error', reject);
    });
  }
  return tmpPath;
}

async function resolveAndDownload(item, source) {
  let url = source.url;
  if (source.site === 'coolrom') {
    url = await resolveCoolrom(source.url);
  }
  const tmpPath = await downloadFile(item, url);
  if (tmpPath.endsWith('.7z') || tmpPath.endsWith('.zip') || tmpPath.endsWith('.rar')) {
    await extractWith7z(tmpPath, PSX_DIR);
    fs.unlinkSync(tmpPath);
  }
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
    log.info(`Download ${item.serial} de ${source.site}: ${source.url}`);
    await resolveAndDownload(item, source);
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

process.on('uncaughtException', (e) => log.error(`uncaught: ${e.message}`));
process.on('unhandledRejection', (e) => log.error(`rejection: ${e.message}`));

app.get('/dashboard', (req, res) => res.sendFile(path.join(__dirname, 'dashboard.html')));
app.get('/queue-proxy', async (req, res) => {
  try {
    const r = await axios.get(`http://127.0.0.1:${PORTS.QUEUE}/queue`, { timeout: 3000 });
    res.json(r.data);
  } catch (e) { res.json({ error: e.message }); }
});

app.listen(PORTS.DOWNLOAD, '127.0.0.1', () => {
  log.info(`Download service em http://127.0.0.1:${PORTS.DOWNLOAD}`);
  loop();
});
