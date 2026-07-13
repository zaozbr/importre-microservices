const express = require('express');
const axios = require('axios');
const { spawn } = require('child_process');
const path = require('path');
const { PORTS } = require('../shared/config');
const Logger = require('../shared/logger');

const log = new Logger('orchestrator');
const app = express();
app.use(express.json());

const ROOT = path.dirname(__dirname);
const services = {};

function startService(name, script) {
  const proc = spawn('node', [script], { cwd: ROOT });
  services[name] = proc;
  proc.stdout.on('data', d => { try { log.info(`[${name}] ${d.toString().trim()}`); } catch (e) {} });
  proc.stdout.on('error', () => {});
  proc.stderr.on('data', d => { try { log.error(`[${name}] ${d.toString().trim()}`); } catch (e) {} });
  proc.stderr.on('error', () => {});
  proc.on('exit', (code) => {
    log.warn(`[${name}] saiu com code ${code}. Reiniciando em 30s...`);
    delete services[name];
    setTimeout(() => startService(name, script), 30000);
  });
}

async function serviceStatus(port) {
  try {
    const res = await axios.get(`http://127.0.0.1:${port}/status`, { timeout: 2000 });
    return res.data;
  } catch (e) {
    return { error: e.message };
  }
}

app.get('/status', async (req, res) => {
  res.json({
    queue: await serviceStatus(PORTS.QUEUE),
    search: await serviceStatus(PORTS.SEARCH),
    download: await serviceStatus(PORTS.DOWNLOAD),
    chd: await serviceStatus(PORTS.CHD)
  });
});

app.get('/', async (req, res) => {
  const status = await serviceStatus(PORTS.QUEUE);
  res.send(`
    <h1>importre-microservices</h1>
    <p>Queue: pending=${status.pending || '?'}, in_progress=${status.in_progress || '?'}, completed=${status.completed || '?'}, failed=${status.failed || '?'}</p>
    <p><a href="/status">Status JSON</a></p>
  `);
});

process.on('uncaughtException', (e) => log.error(`uncaught: ${e.message}`));
process.on('unhandledRejection', (e) => log.error(`rejection: ${e.message}`));

app.listen(PORTS.ORCHESTRATOR, '127.0.0.1', () => {
  log.info(`Orchestrator em http://127.0.0.1:${PORTS.ORCHESTRATOR}`);
  startService('queue', 'services/queue/index.js');
  startService('search', 'services/search/index.js');
  startService('download', 'services/download/index.js');
  startService('chd', 'services/chd/index.js');
});
