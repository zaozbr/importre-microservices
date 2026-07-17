const express = require('express');
const axios = require('axios');
const fs = require('fs');
const { spawn, exec } = require('child_process');
const path = require('path');
const { PORTS, LOG_PATH, PSX_DIR, QUEUE_PATH, WORKERS } = require('../shared/config');
const Logger = require('../shared/logger');

const log = new Logger('orchestrator');
const app = express();

// Scripts dos servicos (evita duplicacao de string)
const SCRIPTS = {
  queue: 'services/queue/index.js',
  search: 'services/search/index.js',
  download: 'services/download/index.js',
  chd: 'services/chd/index.js'
};
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
  const heap = name === 'download' ? '12288' : '4096';
  const proc = spawn('node', [`--max-old-space-size=${heap}`, script], {
    cwd: ROOT,
    stdio: ['ignore', 'pipe', 'pipe']
  });
  services[name] = proc;
  // Handler seguro: ignora EPIPE e erros de stream silenciosamente
  proc.stdout.on('data', d => {
    try {
      const msg = d.toString().trim();
      if (msg) log.info('[' + name + '] ' + msg);
    } catch (e) { /* EPIPE ou stream fechado - ignorar */ }
  });
  proc.stdout.on('error', () => {});
  proc.stderr.on('data', d => {
    try {
      const msg = d.toString().trim();
      if (msg) log.error('[' + name + '] ' + msg);
    } catch (e) { /* EPIPE ou stream fechado - ignorar */ }
  });
  proc.stderr.on('error', () => {});
  proc.on('exit', (code) => {
    try { log.warn('[' + name + '] saiu com code ' + code + '.'); } catch (e) {}
    delete services[name];
    if (controlState !== 'stopped') {
      setTimeout(() => startService(name, script), 30000);
    }
  });
  proc.on('error', () => { /* spawn error - ignorar */ });
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
  // Buscar globalStat do aria2 em paralelo com status dos servicos
  const rpcSpeedPromise = axios.post(ARIA2_RPC, {
    jsonrpc: '2.0', method: 'aria2.getGlobalStat', id: 'stat', params: ARIA2_TOKEN
  }, { timeout: 3000 }).then(r => r.data.result).catch(() => ({ downloadSpeed: '0', uploadSpeed: '0', numActive: '0', numWaiting: '0' }));

  const [queueStatus, searchStatus, downloadStatus, chdStatus, rpcSpeed] = await Promise.all([
    serviceGet(PORTS.QUEUE, '/status'),
    serviceGet(PORTS.SEARCH, '/status'),
    serviceGet(PORTS.DOWNLOAD, '/status'),
    serviceGet(PORTS.CHD, '/status'),
    rpcSpeedPromise
  ]);

  res.json({
    queue: queueStatus,
    search: searchStatus,
    download: downloadStatus,
    chd: chdStatus,
    control: controlState,
    globalSpeed: {
      download: parseInt(rpcSpeed.downloadSpeed || '0', 10),
      upload: parseInt(rpcSpeed.uploadSpeed || '0', 10),
      numActive: parseInt(rpcSpeed.numActive || '0', 10),
      numWaiting: parseInt(rpcSpeed.numWaiting || '0', 10)
    }
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

// Limpa itens presos com retry_count alto (>= 50) que estao em loop infinito
// Move para status "failed" permanentemente
app.post('/api/clear-stuck', async (req, res) => {
  const maxRetry = parseInt(req.body?.maxRetry) || 50;
  const result = await servicePost(PORTS.QUEUE, '/clear-stuck', { maxRetry });
  res.json(result);
});

// === APIs de acoes por item ===

// Detalhes completos de um item (queue + aria2 + sources)
const ARIA2_RPC = 'http://127.0.0.1:6800/jsonrpc';
const ARIA2_TOKEN = ['token:devin'];

app.get('/api/item/:serial/details', async (req, res) => {
  const { serial } = req.params;
  try {
    const qData = await serviceGet(PORTS.QUEUE, '/queue');
    const item = (qData.queue || []).find(i => i.serial === serial);
    if (!item) return res.status(404).json({ error: 'item not found' });

    // Buscar tasks aria2 relacionadas
    let aria2Tasks = [];
    try {
      const axios = require('axios');
      const [active, waiting, stopped] = await Promise.all([
        axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.tellActive', id: 'd', params: ARIA2_TOKEN }),
        axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.tellWaiting', id: 'd', params: [...ARIA2_TOKEN, 0, 50] }),
        axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.tellStopped', id: 'd', params: [...ARIA2_TOKEN, 0, 50] }),
      ]);
      const all = [...(active.data.result || []), ...(waiting.data.result || []), ...(stopped.data.result || [])];
      aria2Tasks = all.filter(t => {
        const f = t.files?.[0];
        return f && (f.path?.includes(serial) || f.uris?.[0]?.uri?.includes(serial));
      });
    } catch {}

    res.json({ item, aria2Tasks });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Tentar novamente: recoloca item em pending
app.post('/api/item/:serial/retry', async (req, res) => {
  const { serial } = req.params;
  try {
    const qData = await serviceGet(PORTS.QUEUE, '/queue');
    const item = (qData.queue || []).find(i => i.serial === serial);
    if (!item) return res.status(404).json({ error: 'item not found' });
    item.status = 'pending';
    item.retry_count = (item.retry_count || 0) + 1;
    item.last_retry = new Date().toISOString();
    delete item.sources;
    delete item.cooldown_until;
    await servicePost(PORTS.QUEUE, '/queue/update', { serial, updates: { status: 'pending', retry_count: item.retry_count, last_retry: item.last_retry } });
    log.info(`[MANUAL] Retry solicitado para ${serial}`);
    res.json({ ok: true, serial, status: 'pending' });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Procurar novamente: dispara busca manual por outras fontes
app.post('/api/item/:serial/search', async (req, res) => {
  const { serial } = req.params;
  try {
    const qData = await serviceGet(PORTS.QUEUE, '/queue');
    const item = (qData.queue || []).find(i => i.serial === serial);
    if (!item) return res.status(404).json({ error: 'item not found' });
    item.status = 'searching';
    delete item.sources;
    delete item.cooldown_until;
    await servicePost(PORTS.QUEUE, '/queue/update', { serial, updates: { status: 'searching' } });
    log.info(`[MANUAL] Busca manual solicitada para ${serial}`);
    res.json({ ok: true, serial, status: 'searching' });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Requeue: volta item para cooldown
app.post('/api/item/:serial/requeue', async (req, res) => {
  const { serial } = req.params;
  const result = await servicePost(PORTS.QUEUE, '/queue/requeue', { serial });
  log.info(`[MANUAL] Requeue solicitado para ${serial}`);
  res.json(result);
});

// Multi-source forçado: marca item para agrupar fontes mesmo com size diferente
app.post('/api/item/:serial/multisource', async (req, res) => {
  const { serial } = req.params;
  try {
    const qData = await serviceGet(PORTS.QUEUE, '/queue');
    const item = (qData.queue || []).find(i => i.serial === serial);
    if (!item) return res.status(404).json({ error: 'item not found' });
    item.force_multisource = true;
    item.status = 'ready';
    delete item.cooldown_until;
    await servicePost(PORTS.QUEUE, '/queue/update', { serial, updates: { status: 'ready', force_multisource: true } });
    log.info(`[MANUAL] Multi-source forçado para ${serial}`);
    res.json({ ok: true, serial, force_multisource: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Cancelar download: remove do aria2 e volta para pending
app.post('/api/item/:serial/cancel', async (req, res) => {
  const { serial } = req.params;
  try {
    // Remover tasks aria2 relacionadas
    const axios = require('axios');
    const active = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.tellActive', id: 'd', params: ARIA2_TOKEN });
    for (const t of (active.data.result || [])) {
      const f = t.files?.[0];
      if (f && (f.path?.includes(serial) || f.uris?.[0]?.uri?.includes(serial))) {
        await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.remove', id: 'd', params: [...ARIA2_TOKEN, t.gid] });
      }
    }
    // Voltar para pending
    await servicePost(PORTS.QUEUE, '/queue/update', { serial, updates: { status: 'pending' } });
    log.info(`[MANUAL] Cancel solicitado para ${serial}`);
    res.json({ ok: true, serial, status: 'pending' });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Acoes aria2 por GID
app.post('/api/aria2/pause/:gid', async (req, res) => {
  try {
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.pause', id: 'd', params: [...ARIA2_TOKEN, req.params.gid] });
    res.json({ ok: true, result: r.data.result });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/aria2/unpause/:gid', async (req, res) => {
  try {
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.unpause', id: 'd', params: [...ARIA2_TOKEN, req.params.gid] });
    res.json({ ok: true, result: r.data.result });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/aria2/remove/:gid', async (req, res) => {
  try {
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.removeResult', id: 'd', params: [...ARIA2_TOKEN, req.params.gid] });
    res.json({ ok: true, result: r.data.result });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

// === APIs aria2 estendidas (peers, files, servers, options) ===

app.post('/api/aria2/peers/:gid', async (req, res) => {
  try {
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.getPeers', id: 'd', params: [...ARIA2_TOKEN, req.params.gid] });
    res.json({ peers: r.data.result || [] });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/aria2/files/:gid', async (req, res) => {
  try {
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.getFiles', id: 'd', params: [...ARIA2_TOKEN, req.params.gid] });
    res.json({ files: r.data.result || [] });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/aria2/servers/:gid', async (req, res) => {
  try {
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.getServers', id: 'd', params: [...ARIA2_TOKEN, req.params.gid] });
    res.json({ servers: r.data.result || [] });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/aria2/option/:gid', async (req, res) => {
  try {
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.getOption', id: 'd', params: [...ARIA2_TOKEN, req.params.gid] });
    res.json({ option: r.data.result || {} });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/aria2/change-option/:gid', async (req, res) => {
  try {
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.changeOption', id: 'd', params: [...ARIA2_TOKEN, req.params.gid, req.body] });
    res.json({ ok: true, result: r.data.result });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.get('/api/aria2/global-option', async (req, res) => {
  try {
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.getGlobalOption', id: 'd', params: ARIA2_TOKEN });
    res.json({ option: r.data.result || {} });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/aria2/change-global-option', async (req, res) => {
  try {
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.changeGlobalOption', id: 'd', params: [...ARIA2_TOKEN, req.body] });
    res.json({ ok: true, result: r.data.result });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/aria2/add-uri', async (req, res) => {
  try {
    const { uris, options } = req.body;
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.addUri', id: 'd', params: [...ARIA2_TOKEN, uris, options || {}] });
    res.json({ ok: true, gid: r.data.result });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/aria2/add-torrent', async (req, res) => {
  try {
    const { torrent, options } = req.body;
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.addTorrent', id: 'd', params: [...ARIA2_TOKEN, torrent, [], options || {}] });
    res.json({ ok: true, gid: r.data.result });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/aria2/change-position/:gid', async (req, res) => {
  try {
    const { pos, how } = req.body;
    const axios = require('axios');
    const r = await axios.post(ARIA2_RPC, { jsonrpc: '2.0', method: 'aria2.changePosition', id: 'd', params: [...ARIA2_TOKEN, req.params.gid, pos || 0, how || 'POS_SET'] });
    res.json({ ok: true, result: r.data.result });
  } catch (e) { res.status(500).json({ error: e.message }); }
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
      startService('queue', SCRIPTS.queue);
      startService('search', SCRIPTS.search);
      startService('download', SCRIPTS.download);
      startService('chd', SCRIPTS.chd);
    }, 2000);
  }
});

// Servir arquivos estaticos do build React (dashboard v5)
const PUBLIC_DIR = path.join(__dirname, 'public');
if (fs.existsSync(path.join(PUBLIC_DIR, 'index.html'))) {
  app.use(express.static(PUBLIC_DIR, { maxAge: '1h' }));
  // Catch-all para SPA (deep linking funciona)
  app.get('*', (req, res) => {
    res.sendFile(path.join(PUBLIC_DIR, 'index.html'));
  });
} else {
  app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'shell.html'));
  });
}
app.get('/legacy', (req, res) => {
  res.sendFile(path.join(__dirname, 'shell.html'));
});

// Proxy para aria2 RPC (contorna CORS)
app.post('/aria2', async (req, res) => {
  try {
    const rpcRes = await axios.post(ARIA2_RPC, req.body, {
      headers: { 'Content-Type': 'application/json' },
      timeout: 10000,
    });
    res.json(rpcRes.data);
  } catch (e) {
    res.status(502).json({ error: e.message });
  }
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

let lastDlCompleted = 0;
let lastDlCompletedTime = Date.now();

async function performanceWatchdog() {
  if (controlState === 'stopped' || controlState === 'paused') return;
  try {
    const q = await serviceGet(PORTS.QUEUE, '/status');
    const dl = await serviceGet(PORTS.DOWNLOAD, '/status');
    const active = dl.active || 0;
    const dlCompleted = dl.completed || 0;
    const ready = q.ready || 0;
    const pending = q.pending || 0;
    const searching = q.searching || 0;
    const failed = q.failed || 0;
    const queueCompleted = q.completed || 0;

    log.info(`[WATCHDOG-5m] downloads=${active} ready=${ready} pending=${pending} searching=${searching} failed=${failed} completed=${queueCompleted}`);

    // Detecta estagnacao: se completed do download service nao mudou em 5min e tem ready
    if (dlCompleted === lastDlCompleted && ready > 0 && active > 0) {
      const stagnantMs = Date.now() - lastDlCompletedTime;
      log.warn(`[WATCHDOG-5m] ESTAGNACAO: 0 completos em ${(stagnantMs/1000).toFixed(0)}s. Reiniciando download service...`);
      const proc = services['download'];
      if (proc && proc.pid) await killByPid(proc.pid);
      await killProcessByPort(PORTS.DOWNLOAD);
      startService('download', SCRIPTS.download);
      lastDlCompletedTime = Date.now();
    } else if (dlCompleted !== lastDlCompleted) {
      lastDlCompleted = dlCompleted;
      lastDlCompletedTime = Date.now();
    }

    if (ready === 0 && pending > 0 && searching < WORKERS.SEARCH) {
      log.warn('[WATCHDOG-5m] fila pronta vazia e busca subutilizada. Reiniciando search service...');
      const proc = services['search'];
      if (proc && proc.pid) await killByPid(proc.pid);
      await killProcessByPort(PORTS.SEARCH);
      startService('search', SCRIPTS.search);
    }

    if (active < WORKERS.DOWNLOAD / 2 && ready > 0) {
      log.warn('[WATCHDOG-5m] poucos downloads ativos. Reiniciando download service...');
      const proc = services['download'];
      if (proc && proc.pid) await killByPid(proc.pid);
      await killProcessByPort(PORTS.DOWNLOAD);
      startService('download', SCRIPTS.download);
    }

    if (failed > 0 && ready < WORKERS.DOWNLOAD) {
      log.info('[WATCHDOG-5m] reprocessando falhas para aumentar pool de fontes...');
      await servicePost(PORTS.QUEUE, '/reprocess-failures', {});
    }

    if (active > 0 && ready === 0 && pending === 0) {
      log.warn('[WATCHDOG-5m] downloads ativos mas sem fila futura. Verificar velocidade individual no log.');
    }
  } catch (e) {
    log.error('[WATCHDOG-5m] erro: ' + e.message);
  }
}

setInterval(checkAutoReprocess, 30000);
setInterval(performanceWatchdog, 2 * 60 * 1000);

async function healthCheck() {
  if (controlState === 'stopped') return;
  const checks = [
    { name: 'download', port: PORTS.DOWNLOAD, script: SCRIPTS.download },
    { name: 'queue', port: PORTS.QUEUE, script: SCRIPTS.queue },
    { name: 'search', port: PORTS.SEARCH, script: SCRIPTS.search }
  ];
  for (const svc of checks) {
    try {
      const res = await axios.get('http://127.0.0.1:' + svc.port + '/status', { timeout: 5000 });
      if (res.data && !res.data.error) continue;
      throw new Error('resposta invalida');
    } catch (e) {
      log.warn('[HEALTHCHECK-30s] ' + svc.name + ' service nao responde em /status (' + e.message + '). Reiniciando...');
      const proc = services[svc.name];
      if (proc && proc.pid) await killByPid(proc.pid);
      await killProcessByPort(svc.port);
      if (controlState !== 'stopped') {
        startService(svc.name, svc.script);
      }
    }
  }
}

setInterval(healthCheck, 30000);

// Handler robusto: EPIPE é benigno (pipe de processo filho morto), nunca derruba o orchestrator
process.on('uncaughtException', (e) => {
  if (e && e.code === 'EPIPE') return; // Ignorar EPIPE silenciosamente
  try { log.error('uncaught: ' + (e?.message || e)); } catch (logErr) {}
});
process.on('unhandledRejection', (e) => {
  try { log.error('rejection: ' + (e?.message || e)); } catch (logErr) {}
});

app.listen(PORTS.ORCHESTRATOR, '127.0.0.1', () => {
  log.info('Orchestrator em http://127.0.0.1:' + PORTS.ORCHESTRATOR);
  startService('queue', SCRIPTS.queue);
  startService('search', SCRIPTS.search);
  startService('download', SCRIPTS.download);
  startService('chd', SCRIPTS.chd);
});
