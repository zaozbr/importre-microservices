const express = require('express');
const axios = require('axios');
const { PORTS } = require('../../shared/config');
const Logger = require('../../shared/logger');
const { searchAll } = require('./sites');

const log = new Logger('search-service');
const app = express();
app.use(express.json());

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

async function loop() {
  while (true) {
    while (await processOne()) {}
    await new Promise(r => setTimeout(r, 5000));
  }
}

app.get('/status', (req, res) => res.json({ ok: true }));

process.on('uncaughtException', (e) => log.error(`uncaught: ${e.message}`));
process.on('unhandledRejection', (e) => log.error(`rejection: ${e.message}`));

app.listen(PORTS.SEARCH, '127.0.0.1', () => {
  log.info(`Search service em http://127.0.0.1:${PORTS.SEARCH}`);
  loop();
});
