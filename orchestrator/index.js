const express = require('express');
const axios = require('axios');
const fs = require('fs');
const { spawn } = require('child_process');
const path = require('path');
const { PORTS, LOG_PATH, PSX_DIR, STATE_DIR } = require('../shared/config');
const Logger = require('../shared/logger');

const log = new Logger('orchestrator');
const app = express();
app.use(express.json());

const ROOT = path.dirname(__dirname);
const services = {};
let controlState = 'running';

function startService(name, script) {
  if (controlState === 'stopped') return;
  const proc = spawn('node', [script], { cwd: ROOT });
  services[name] = proc;
  proc.stdout.on('data', d => { try { log.info(`[${name}] ${d.toString().trim()}`); } catch (e) {} });
  proc.stdout.on('error', () => {});
  proc.stderr.on('data', d => { try { log.error(`[${name}] ${d.toString().trim()}`); } catch (e) {} });
  proc.stderr.on('error', () => {});
  proc.on('exit', (code) => {
    log.warn(`[${name}] saiu com code ${code}.`);
    delete services[name];
    if (controlState !== 'stopped') {
      setTimeout(() => startService(name, script), 30000);
    }
  });
}

async function serviceGet(port, endpoint) {
  try {
    const res = await axios.get(`http://127.0.0.1:${port}${endpoint}`, { timeout: 3000 });
    return res.data;
  } catch (e) {
    return { error: e.message };
  }
}

async function servicePost(port, endpoint, body) {
  try {
    const res = await axios.post(`http://127.0.0.1:${port}${endpoint}`, body, { timeout: 3000 });
    return res.data;
  } catch (e) {
    return { error: e.message };
  }
}

app.get('/api/status', async (req, res) => {
  res.json({
    queue: await serviceGet(PORTS.QUEUE, '/status'),
    search: await serviceGet(PORTS.SEARCH, '/status'),
    download: await serviceGet(PORTS.DOWNLOAD, '/status'),
    chd: await serviceGet(PORTS.CHD, '/status'),
    control: controlState
  });
});

app.get('/api/queue', async (req, res) => {
  res.json(await serviceGet(PORTS.QUEUE, '/queue'));
});

app.get('/api/log', async (req, res) => {
  try {
    const lines = fs.readFileSync(LOG_PATH, 'utf-8').split('\n').filter(Boolean).slice(-100).reverse();
    res.json({ lines });
  } catch (e) {
    res.json({ error: e.message });
  }
});

app.get('/api/chds', async (req, res) => {
  try {
    const chds = fs.readdirSync(PSX_DIR).filter(f => f.endsWith('.chd')).length;
    res.json({ chds });
  } catch (e) {
    res.json({ error: e.message });
  }
});

app.post('/api/reprocess-failures', async (req, res) => {
  res.json(await servicePost(PORTS.QUEUE, '/reprocess-failures', {}));
});

app.get('/api/control/:action', async (req, res) => {
  const { action } = req.params;
  const valid = ['pause', 'resume', 'restart', 'stop'];
  if (!valid.includes(action)) return res.status(400).json({ error: 'invalid action' });

  controlState = action === 'stop' ? 'stopped' : action === 'pause' ? 'paused' : 'running';
  if (action === 'pause') {
    await servicePost(PORTS.QUEUE, '/pause', {});
  } else if (action === 'resume') {
    await servicePost(PORTS.QUEUE, '/resume', {});
  } else if (action === 'restart') {
    Object.values(services).forEach(p => p.kill('SIGTERM'));
    setTimeout(() => {
      startService('queue', 'services/queue/index.js');
      startService('search', 'services/search/index.js');
      startService('download', 'services/download/index.js');
      startService('chd', 'services/chd/index.js');
    }, 2000);
  } else if (action === 'stop') {
    Object.values(services).forEach(p => p.kill('SIGTERM'));
  }
  res.json({ ok: true, state: controlState });
});

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'shell.html'));
});
app.get('/legacy', (req, res) => {
  res.sendFile(path.join(__dirname, 'dashboard.html'));
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
