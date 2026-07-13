const express = require('express');
const axios = require('axios');
const fs = require('fs');
const { spawn, exec } = require('child_process');
const path = require('path');
const { PORTS, LOG_PATH, PSX_DIR, STATE_DIR, QUEUE_PATH } = require('../shared/config');
const Logger = require('../shared/logger');

const log = new Logger('orchestrator');
const app = express();
app.use(express.json());

const ROOT = path.dirname(__dirname);
const services = {};
let controlState = 'running';

function execPromise(cmd) {
  return new Promise((resolve) => {
    exec(cmd, { windowsHide: true }, (err, stdout, stderr) => resolve({ err, stdout, stderr }));
  });
}

function loadQueue() {
  if (!fs.existsSync(QUEUE_PATH)) return { queue: [], in_progress: {}, completed: {}, failed: {} };
  try { return JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8')); }
  catch (e) { return { queue: [], in_progress: {}, completed: {}, failed: {} }; }
}

function saveQueue(data) {
  fs.writeFileSync(QUEUE_PATH, JSON.stringify(data, null, 2), 'utf-8');
}

function cleanupInProgress() {
  try {
    const q = loadQueue();
    let cleaned = 0;
    for (const serial of Object.keys(q.in_progress || {})) {
      const item = q.queue.find(i => i.serial === serial);
      if (item && !['completed'].includes(item.status)) {
        item.status = 'pending';
        item.retry_count = (item.retry_count || 0) + 1;
        item.last_error = 'stopped by user';
        item.last_failed = new Date().toISOString();
        cleaned++;
      }
    }
    q.in_progress = {};
    saveQueue(q);
    return cleaned;
  } catch (e) {
    log.error('cleanupInProgress error: ' + e.message);
    return 0;
  }
}

async function killByPid(pid) {
  try { process.kill(pid, 'SIGTERM'); } catch (e) {}
  await new Promise(r => setTimeout(r, 1000));
  try { await execPromise('taskkill /F /PID ' + pid); } catch (e) {}
}

async function killServiceProcesses() {
  const killed = [];
  for (const [name, proc] of Object.entries(services)) {
    if (proc && proc.pid) {
      await killByPid(proc.pid);
      killed.push(name);
      delete services[name];
    }
  }
  return killed;
}

async function getPortPids(port) {
  const pids = new Set();
  try {
    const { stdout } = await execPromise('netstat -ano | findstr :' + port);
    for (const line of stdout.split('\n').filter(Boolean)) {
      const parts = line.trim().split(/\s+/);
      const pid = parts[parts.length - 1];
      if (pid && !isNaN(parseInt(pid))) pids.add(parseInt(pid));
    }
  } catch (e) {}
  return [...pids];
}

async function killProcessByPort(port) {
  const pids = await getPortPids(port);
  for (const pid of pids) {
    if (pid === process.pid) continue;
    try { await execPromise('taskkill /F /PID ' + pid); } catch (e) {}
  }
}

async function killAria2() {
  try { await execPromise('taskkill /F /IM aria2c.exe'); } catch (e) {}
}

async function checkPortFree(port) {
  try {
    const { stdout } = await execPromise('netstat -ano | findstr :' + port);
    return !stdout.trim();
  } catch (e) { return true; }
}

async function killAndCleanup(includeOrchestrator = false) {
  controlState = 'stopped';
  log.info('STOP/RESTART: iniciando rotina de cleanup...');
  const killed = await killServiceProcesses();
  for (const [name, port] of Object.entries(PORTS)) {
    if (name === 'ORCHESTRATOR' && !includeOrchestrator) continue;
    await killProcessByPort(port);
  }
  await killAria2();
  await new Promise(r => setTimeout(r, 3000));
  const servicePorts = Object.entries(PORTS).filter(([name]) => name !== 'ORCHESTRATOR').map(([, port]) => port);
  let attempts = 0;
  while (attempts < 30) {
    const allFree = (await Promise.all(servicePorts.map(checkPortFree))).every(Boolean);
    if (allFree) break;
    for (const [name, port] of Object.entries(PORTS)) {
      if (name === 'ORCHESTRATOR' && !includeOrchestrator) continue;
      await killProcessByPort(port);
    }
    await new Promise(r => setTimeout(r, 1000));
    attempts++;
  }
  const cleaned = cleanupInProgress();
  log.info('STOP/RESTART: ' + killed.length + ' servicos mortos, ' + cleaned + ' in_progress limpos');
  return { killed, cleaned, portsFree: attempts < 30 };
}

function shutdownOrchestrator(delay = 1000) {
  setTimeout(() => {
    log.info('STOP/RESTART: encerrando orchestrator.');
    process.exit(0);
  }, delay);
}

function startService(name, script) {
  if (controlState === 'stopped') return;
  const proc = spawn('node', [script], { cwd: ROOT });
  services[name] = proc;
  proc.stdout.on('data', d => { try { log.info('[' + name + '] ' + d.toString().trim()); } catch (e) {} });
  proc.stdout.on('error', () => {});
  proc.stderr.on('data', d => { try { log.error('[' + name + '] ' + d.toString().trim()); } catch (e) {} });
  proc.stderr.on('error', () => {});
  proc.on('exit', (code) => {
    log.warn('[' + name + '] saiu com code ' + code + '.');
    delete services[name];
    if (controlState !== 'stopped') {
      setTimeout(() => startService(name, script), 30000);
    }
  });
}

async function serviceGet(port, endpoint) {
  try {
    const res = await axios.get('http://127.0.0.1:' + port + endpoint, { timeout: 3000 });
    return res.data;
  } catch (e) {
    return { error: e.message };
  }
}

async function servicePost(port, endpoint, body) {
  try {
    const res = await axios.post('http://127.0.0.1:' + port + endpoint, body, { timeout: 3000 });
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

  if (action === 'pause') {
    controlState = 'paused';
    await servicePost(PORTS.QUEUE, '/pause', {});
    res.json({ ok: true, state: controlState });
  } else if (action === 'resume') {
    controlState = 'running';
    await servicePost(PORTS.QUEUE, '/resume', {});
    res.json({ ok: true, state: controlState });
  } else if (action === 'stop') {
    const result = await killAndCleanup(false);
    res.json({ ok: true, state: 'stopped', result });
    shutdownOrchestrator(500);
  } else if (action === 'restart') {
    const result = await killAndCleanup(false);
    res.json({ ok: true, state: 'restarting', result });
    setTimeout(() => {
      controlState = 'running';
      startService('queue', 'services/queue/index.js');
      startService('search', 'services/search/index.js');
      startService('download', 'services/download/index.js');
      startService('chd', 'services/chd/index.js');
    }, 2000);
  }
});

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'shell.html'));
});
app.get('/legacy', (req, res) => {
  res.sendFile(path.join(__dirname, 'dashboard.html'));
});

async function checkAutoReprocess() {
  if (controlState === 'stopped' || controlState === 'paused') return;
  try {
    const q = await serviceGet(PORTS.QUEUE, '/status');
    const active = (q.pending || 0) + (q.searching || 0) + (q.ready || 0) + (q.downloading || 0);
    const failed = q.failed || 0;
    if (active === 0 && failed > 0) {
      log.info('Fila ativa vazia (' + failed + ' falhas). Reprocessando falhas automaticamente...');
      await servicePost(PORTS.QUEUE, '/reprocess-failures', {});
    }
  } catch (e) {
    log.error('Auto-reprocess check failed: ' + e.message);
  }
}

setInterval(checkAutoReprocess, 30000);

process.on('uncaughtException', (e) => log.error('uncaught: ' + e.message));
process.on('unhandledRejection', (e) => log.error('rejection: ' + e.message));

app.listen(PORTS.ORCHESTRATOR, '127.0.0.1', () => {
  log.info('Orchestrator em http://127.0.0.1:' + PORTS.ORCHESTRATOR);
  startService('queue', 'services/queue/index.js');
  startService('search', 'services/search/index.js');
  startService('download', 'services/download/index.js');
  startService('chd', 'services/chd/index.js');
});
