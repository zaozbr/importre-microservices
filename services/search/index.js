const express = require('express');
const axios = require('axios');
const path = require('path');
const { PORTS, WORKERS } = require('../../shared/config');
const Logger = require('../../shared/logger');
const { searchAll, listPlugins } = require('./sites');

const log = new Logger('search-service');
const app = express();
app.use(express.json());
app.use('/shared', express.static(path.join(__dirname, '..', '..', 'shared')));

const QUEUE_URL = `http://127.0.0.1:${PORTS.QUEUE}`;

async function queueRequest(method, endpoint, body) {
  const res = await axios({ method, url: `${QUEUE_URL}${endpoint}`, data: body, timeout: 5000 });
  return res.data;
}

async function processOne() {
  const { item } = await queueRequest('post', '/queue/next-pending');
  if (!item) return false;

  log.info(`Buscando ${item.serial}`);
  const sources = await searchAll(item.serial, item.title);

  if (!sources.length) {
    await queueRequest('post', '/queue/fail', { serial: item.serial, reason: 'nenhuma fonte encontrada' });
    return true;
  }

  await queueRequest('post', '/queue/ready', { serial: item.serial, sources });
  log.info(`Ready ${item.serial}: ${sources.length} fontes (${sources.map(s => s.site).join(', ')})`);
  return true;
}

async function workerLoop(id) {
  while (true) {
    const hadWork = await processOne();
    if (!hadWork) await new Promise(r => setTimeout(r, 2000));
  }
}

async function feedWatchdog() {
  while (true) {
    await new Promise(r => setTimeout(r, 30000));
    try {
      const q = await queueRequest('get', '/status');
      const ready = q.ready || 0;
      const pending = q.pending || 0;
      const downloading = q.downloading || 0;
      const searchWorkers = Math.max(1, WORKERS.SEARCH || 1);
      log.info(`[WATCHDOG] search: pendentes=${pending} buscando=${q.searching||0} prontos=${ready} downloads=${downloading} workers=${searchWorkers}`);
      if (ready === 0 && pending > 0 && (q.searching || 0) < searchWorkers) {
        log.warn(`[WATCHDOG] fila pronta vazia com ${pending} pendentes. Aumentando pressao de busca.`);
      }
      if (ready < WORKERS.DOWNLOAD && pending > 0) {
        log.warn(`[WATCHDOG] prontos=${ready} insuficiente para downloads=${WORKERS.DOWNLOAD}. Necessario mais fontes.`);
      }
    } catch (e) { log.error(`[WATCHDOG] erro: ${e.message}`); }
  }
}

async function loop() {
  const workers = Math.max(1, WORKERS.SEARCH || 1);
  log.info(`Iniciando ${workers} workers de busca`);
  feedWatchdog();
  await Promise.all(Array.from({ length: workers }, (_, i) => workerLoop(i)));
}

app.get('/status', (req, res) => res.json({ ok: true, plugins: listPlugins() }));

process.on('uncaughtException', (e) => log.error(`uncaught: ${e.message}`));
process.on('unhandledRejection', (e) => log.error(`rejection: ${e.message}`));

app.get('/dashboard', (req, res) => res.sendFile(path.join(__dirname, 'dashboard.html')));
app.get('/queue-proxy', async (req, res) => {
  try {
    const r = await axios.get(`http://127.0.0.1:${PORTS.QUEUE}/queue`, { timeout: 3000 });
    res.json(r.data);
  } catch (e) { res.json({ error: e.message }); }
});

app.listen(PORTS.SEARCH, '127.0.0.1', () => {
  log.info(`Search service em http://127.0.0.1:${PORTS.SEARCH}`);
  loop();
});
