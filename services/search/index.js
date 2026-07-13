const express = require('express');
const axios = require('axios');
const { PORTS } = require('../../shared/config');
const Logger = require('../../shared/logger');

const log = new Logger('search-service');
const app = express();
app.use(express.json());

const QUEUE_URL = `http://127.0.0.1:${PORTS.QUEUE}`;

async function queueRequest(method, endpoint, body) {
  const res = await axios({ method, url: `${QUEUE_URL}${endpoint}`, data: body, timeout: 5000 });
  return res.data;
}

async function searchArchive(serial) {
  try {
    const url = `https://archive.org/advancedsearch.php?q=${encodeURIComponent(`"${serial}"`)}&fl%5B%5D=identifier&fl%5B%5D=title&sort=&rows=10&page=1&output=json&save=yes`;
    const res = await axios.get(url, { timeout: 30000 });
    const docs = res.data?.response?.docs || [];
    return docs.map(d => ({
      site: 'archive.org',
      identifier: d.identifier,
      title: d.title,
      url: `https://archive.org/download/${d.identifier}/`
    }));
  } catch (e) {
    log.error(`archive.org search error: ${e.message}`);
    return [];
  }
}

async function processOne() {
  const { item } = await queueRequest('post', '/queue/next-pending');
  if (!item) return false;

  log.info(`Buscando ${item.serial}`);
  const sources = await searchArchive(item.serial);

  if (!sources.length) {
    await queueRequest('post', '/queue/fail', { serial: item.serial, reason: 'nenhuma fonte encontrada' });
    return true;
  }

  await queueRequest('post', '/queue/ready', { serial: item.serial, sources });
  log.info(`Ready ${item.serial}: ${sources.length} fontes`);
  return true;
}

async function loop() {
  while (true) {
    while (await processOne()) {}
    await new Promise(r => setTimeout(r, 10000));
  }
}

app.get('/status', (req, res) => res.json({ ok: true }));

app.listen(PORTS.SEARCH, () => {
  log.info(`Search service em http://127.0.0.1:${PORTS.SEARCH}`);
  loop();
});
