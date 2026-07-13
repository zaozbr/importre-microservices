const express = require('express');
const fs = require('fs');
const path = require('path');
const { QUEUE_PATH, PORTS } = require('../../shared/config');
const Logger = require('../../shared/logger');

const log = new Logger('queue-service');
const app = express();
app.use(express.json());

// === Configuracao de retry ===
// Backoff: 30s, 60s, 2min, 5min, 10min, 20min, 30min (cap)
const MAX_RETRY = 15;
const RETRY_DELAYS = [30000, 60000, 120000, 300000, 600000, 1200000, 1800000];
const RETRY_DELAY_CAP = 1800000; // 30min

let paused = false;

// === Persistencia com backup automatico ===
function loadQueue() {
  if (!fs.existsSync(QUEUE_PATH)) {
    return { queue: [], in_progress: {}, completed: {}, failed: {} };
  }
  try {
    const data = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
    if (!data.queue || !Array.isArray(data.queue)) throw new Error('queue invalida');
    return data;
  } catch (e) {
    log.error(`Erro lendo queue: ${e.message}. Tentando backup...`);
    const bak = QUEUE_PATH + '.bak';
    if (fs.existsSync(bak)) {
      try {
        const data = JSON.parse(fs.readFileSync(bak, 'utf-8'));
        log.info(`Backup restaurado com ${data.queue.length} itens`);
        return data;
      } catch (e2) {
        log.error(`Backup tambem corrompido: ${e2.message}`);
      }
    }
    return { queue: [], in_progress: {}, completed: {}, failed: {} };
  }
}

function saveQueue(data) {
  const tmp = QUEUE_PATH + '.tmp';
  // Backup do arquivo atual antes de sobrescrever
  try {
    if (fs.existsSync(QUEUE_PATH)) {
      fs.copyFileSync(QUEUE_PATH, QUEUE_PATH + '.bak');
    }
  } catch (e) { /* nao critico */ }
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), 'utf-8');
  fs.renameSync(tmp, QUEUE_PATH);
}

// === Cache em memoria com validacao ===
let queueCache = null;
let queueDirty = false;
let lastExternalCheck = 0;
let lastMtime = 0;

function getQueue() {
  if (!queueCache) {
    queueCache = loadQueue();
    try { lastMtime = fs.statSync(QUEUE_PATH).mtimeMs; } catch (e) {}
    return queueCache;
  }
  // Verifica se o arquivo foi modificado externamente a cada 30s
  const now = Date.now();
  if (now - lastExternalCheck > 30000 && !queueDirty) {
    lastExternalCheck = now;
    try {
      const mtime = fs.statSync(QUEUE_PATH).mtimeMs;
      if (mtime !== lastMtime) {
        log.info('Queue.json modificado externamente, recarregando cache...');
        queueCache = loadQueue();
        lastMtime = mtime;
      }
    } catch (e) {}
  }
  return queueCache;
}

function markDirty() {
  queueDirty = true;
}

function persistQueue() {
  if (queueDirty && queueCache) {
    saveQueue(queueCache);
    queueDirty = false;
    try { lastMtime = fs.statSync(QUEUE_PATH).mtimeMs; } catch (e) {}
  }
}

// Persiste a cada 10s (mais frequente para nao perder estado)
setInterval(persistQueue, 10000);
// Persiste no shutdown
process.on('SIGTERM', () => { persistQueue(); process.exit(0); });
process.on('SIGINT', () => { persistQueue(); process.exit(0); });

// === Reservas em memoria ===
const reservedPending = new Set();
const reservedReady = new Set();

function isReady(item) {
  return item.status === 'ready' && (item.sources || []).some(s => s.url);
}

function canRetry(item) {
  const retries = item.retry_count || 0;
  if (retries >= MAX_RETRY) return false;
  const lastFail = item.last_failed ? new Date(item.last_failed).getTime() : 0;
  if (!lastFail) return true; // nunca falhou
  const delay = RETRY_DELAYS[Math.min(retries, RETRY_DELAYS.length - 1)] || RETRY_DELAY_CAP;
  return Date.now() - lastFail >= delay;
}

// === Endpoints ===

app.get('/status', (req, res) => {
  const q = getQueue();
  res.json({
    pending: q.queue.filter(i => i.status === 'pending').length,
    searching: q.queue.filter(i => i.status === 'searching').length,
    ready: q.queue.filter(i => i.status === 'ready').length,
    downloading: q.queue.filter(i => i.status === 'downloading').length,
    in_progress: Object.keys(q.in_progress || {}).length,
    completed: Object.keys(q.completed || {}).length,
    failed: Object.keys(q.failed || {}).length,
    total: q.queue.length,
    paused
  });
});

app.get('/queue', (req, res) => res.json(getQueue()));
app.use('/shared', express.static(path.join(__dirname, '..', '..', 'shared')));
app.get('/dashboard', (req, res) => res.sendFile(path.join(__dirname, 'dashboard.html')));

app.post('/queue/add', (req, res) => {
  const { serial, title, priority = 1 } = req.body;
  if (!serial) return res.status(400).json({ error: 'serial required' });
  const q = getQueue();
  const existing = q.queue.find(i => i.serial === serial);
  if (existing) return res.json({ added: false, item: existing });
  const item = {
    serial,
    title: title || serial,
    status: 'pending',
    priority,
    added: new Date().toISOString(),
    retry_count: 0,
    site_history: {},
    sources: []
  };
  q.queue.push(item);
  markDirty();
  log.info(`Adicionado: ${serial}`);
  res.json({ added: true, item });
});

app.post('/pause', (req, res) => { paused = true; log.info('Queue paused'); res.json({ paused }); });
app.post('/resume', (req, res) => { paused = false; log.info('Queue resumed'); res.json({ paused }); });

// Search service pega um item pending
app.post('/queue/next-pending', (req, res) => {
  if (paused) return res.json({ item: null, paused: true });
  const q = getQueue();
  const pending = q.queue
    .filter(i => i.status === 'pending' && !reservedPending.has(i.serial) && !q.in_progress[i.serial] && !q.completed[i.serial] && canRetry(i))
    .sort((a, b) => (b.priority || 0) - (a.priority || 0));
  if (!pending.length) return res.json({ item: null });
  const item = pending[0];
  reservedPending.add(item.serial);
  item.status = 'searching';
  item.search_started = new Date().toISOString();
  q.in_progress[item.serial] = item;
  markDirty();
  reservedPending.delete(item.serial);
  log.info(`Next pending: ${item.serial}`);
  res.json({ item });
});

// Download service pega um item ready
app.post('/queue/next-ready', (req, res) => {
  if (paused) return res.json({ item: null, paused: true });
  const preferredSite = req.body && req.body.preferredSite;
  const q = getQueue();
  let ready = q.queue
    .filter(i => i.status === 'ready' && isReady(i) && !reservedReady.has(i.serial) && !q.in_progress[i.serial] && !q.completed[i.serial]);
  
  // Funcao de ordenacao: primeiro por % de conclusao (maior primeiro), depois por prioridade
  function sortByProgress(a, b) {
    const pctA = (a.progress && a.progress.percent) || 0;
    const pctB = (b.progress && b.progress.percent) || 0;
    if (pctB !== pctA) return pctB - pctA; // maior % primeiro
    return (b.priority || 0) - (a.priority || 0); // depois prioridade
  }
  
  // Se tem fonte preferida, filtra por ela primeiro
  if (preferredSite && preferredSite !== 'any') {
    const withPref = ready.filter(i => (i.sources || []).some(s => s.site === preferredSite || s.site === preferredSite.replace('.', '_')));
    if (withPref.length > 0) {
      ready = withPref.sort(sortByProgress);
    } else {
      ready = ready.sort(sortByProgress);
    }
  } else {
    ready = ready.sort(sortByProgress);
  }
  
  if (!ready.length) return res.json({ item: null });
  const item = ready[0];
  const pct = (item.progress && item.progress.percent) || 0;
  reservedReady.add(item.serial);
  item.status = 'downloading';
  item.download_started = new Date().toISOString();
  q.in_progress[item.serial] = item;
  markDirty();
  reservedReady.delete(item.serial);
  log.info(`Next ready: ${item.serial} [${pct}%] [fonte pref: ${preferredSite || 'any'}]`);
  res.json({ item });
});

app.post('/queue/ready', (req, res) => {
  const { serial, sources } = req.body;
  const q = getQueue();
  const item = q.queue.find(i => i.serial === serial);
  if (!item) return res.status(404).json({ error: 'not found' });
  item.status = 'ready';
  item.sources = sources || [];
  item.search_ended = new Date().toISOString();
  delete q.in_progress[serial];
  markDirty();
  log.info(`Ready: ${serial} (${item.sources.length} fontes)`);
  res.json({ item });
});

app.post('/queue/update', (req, res) => {
  const { serial, updates } = req.body;
  const q = getQueue();
  const item = q.queue.find(i => i.serial === serial);
  if (!item) return res.status(404).json({ error: 'not found' });
  Object.assign(item, updates);
  if (q.in_progress[serial]) Object.assign(q.in_progress[serial], updates);
  markDirty();
  res.json({ item });
});

app.post('/queue/complete', (req, res) => {
  const { serial } = req.body;
  const q = getQueue();
  const item = q.queue.find(i => i.serial === serial);
  if (item) {
    item.status = 'completed';
    item.completed = new Date().toISOString();
  }
  if (q.in_progress[serial]) {
    q.completed[serial] = q.in_progress[serial];
    delete q.in_progress[serial];
  }
  // Remove de failed se estava la
  if (q.failed && q.failed[serial]) delete q.failed[serial];
  markDirty();
  log.info(`Completado: ${serial}`);
  res.json({ ok: true });
});

app.post('/queue/fail', (req, res) => {
  const { serial, reason } = req.body;
  const q = getQueue();
  const item = q.queue.find(i => i.serial === serial);
  if (item) {
    item.status = 'pending';
    item.retry_count = (item.retry_count || 0) + 1;
    item.last_error = reason;
    item.last_failed = new Date().toISOString();
  }
  if (q.in_progress[serial]) {
    // So move para failed se excedeu MAX_RETRY
    if (item && item.retry_count >= MAX_RETRY) {
      q.failed[serial] = q.in_progress[serial];
      log.warn(`Falhou definitivamente: ${serial} (${item.retry_count} retries) - ${reason}`);
    }
    delete q.in_progress[serial];
  }
  // Move item para o fim da fila para nao bloquear outros
  const idx = q.queue.findIndex(i => i.serial === serial);
  if (idx !== -1) {
    const [failedItem] = q.queue.splice(idx, 1);
    q.queue.push(failedItem);
  }
  markDirty();
  log.warn(`Falhou: ${serial} - ${reason} (retry ${item?.retry_count || 0}) -> fim da fila`);
  res.json({ ok: true });
});

app.post('/reprocess-failures', (req, res) => {
  const q = getQueue();
  let moved = 0;
  for (const serial of Object.keys(q.failed || {})) {
    const item = q.queue.find(i => i.serial === serial);
    if (item) {
      item.retry_count = 0;
      item.last_error = null;
      item.last_failed = null;
      item.status = 'pending';
    } else {
      const failedItem = q.failed[serial];
      if (failedItem) {
        failedItem.retry_count = 0;
        failedItem.last_error = null;
        failedItem.last_failed = null;
        failedItem.status = 'pending';
        q.queue.push(failedItem);
      }
    }
    delete q.failed[serial];
    moved++;
  }
  // Reseta itens com status invalido
  for (const item of q.queue) {
    if (!['pending', 'completed', 'searching', 'downloading', 'ready'].includes(item.status)) {
      item.status = 'pending';
      item.retry_count = 0;
      item.last_error = null;
      item.last_failed = null;
      moved++;
    }
  }
  // Pendentes no fim
  const nonPending = q.queue.filter(i => i.status !== 'pending');
  const pending = q.queue.filter(i => i.status === 'pending');
  q.queue = [...nonPending, ...pending];
  markDirty();
  log.info(`Reprocessar falhas: ${moved} itens resetados`);
  res.json({ ok: true, moved });
});

// === Watchdogs ===

function startQueueDrainWatchdog() {
  const STUCK_DOWNLOAD_MS = 20 * 60 * 1000;
  const STUCK_SEARCH_MS = 10 * 60 * 1000;
  setInterval(() => {
    const q = getQueue();
    let drained = 0;
    const now = Date.now();
    for (const item of q.queue) {
      if (item.status === 'downloading' && item.download_started) {
        const start = new Date(item.download_started).getTime();
        if (now - start > STUCK_DOWNLOAD_MS) {
          item.status = 'ready';
          item.stuck_released = new Date().toISOString();
          item.retry_count = (item.retry_count || 0) + 1;
          delete q.in_progress[item.serial];
          drained++;
        }
      }
      if (item.status === 'searching' && item.search_started) {
        const start = new Date(item.search_started).getTime();
        if (now - start > STUCK_SEARCH_MS) {
          item.status = 'pending';
          item.stuck_released = new Date().toISOString();
          item.retry_count = (item.retry_count || 0) + 1;
          delete q.in_progress[item.serial];
          drained++;
        }
      }
    }
    if (drained) {
      markDirty();
      log.warn(`Queue drain: ${drained} itens presos liberados`);
    }
  }, 60000);
}

// Auto-reprocess de falhas a cada 10min
function startAutoReprocess() {
  setInterval(() => {
    if (paused) return;
    const q = getQueue();
    const failedCount = Object.keys(q.failed || {}).length;
    if (failedCount > 0) {
      log.info(`Auto-reprocess: ${failedCount} falhas serao reprocessadas`);
      for (const serial of Object.keys(q.failed || {})) {
        const item = q.queue.find(i => i.serial === serial);
        if (item) {
          item.retry_count = 0;
          item.last_error = null;
          item.last_failed = null;
          item.status = 'pending';
        } else {
          const failedItem = q.failed[serial];
          if (failedItem) {
            failedItem.retry_count = 0;
            failedItem.last_error = null;
            failedItem.last_failed = null;
            failedItem.status = 'pending';
            q.queue.push(failedItem);
          }
        }
        delete q.failed[serial];
      }
      markDirty();
    }
  }, 10 * 60 * 1000);
}

process.on('uncaughtException', (e) => {
  console.error('uncaughtException', e.stack || e.message);
  log.error(`uncaught: ${e.message}`);
  persistQueue();
  // NAO sai imediatamente - deixa o orchestrator reiniciar se necessario
  // Mas persiste estado para nao perder dados
});
process.on('unhandledRejection', (e) => {
  console.error('unhandledRejection', e.stack || e.message);
  log.error(`rejection: ${e.message}`);
  // NAO sai - rejections nao deveriam derrubar o processo
});

app.listen(PORTS.QUEUE, '127.0.0.1', () => {
  log.info(`Queue service em http://127.0.0.1:${PORTS.QUEUE}`);
  startQueueDrainWatchdog();
  startAutoReprocess();
});
