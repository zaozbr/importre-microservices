const express = require('express');
const fs = require('fs');
const path = require('path');
const { QUEUE_PATH, PORTS } = require('../../shared/config');
const Logger = require('../../shared/logger');

const log = new Logger('queue-service');
const app = express();
app.use(express.json());

const MAX_RETRY = 10;
const RETRY_DELAY_MIN = 5 * 60 * 1000; // 5 min
let paused = false;

function loadQueue() {
  if (!fs.existsSync(QUEUE_PATH)) {
    return { queue: [], in_progress: {}, completed: {}, failed: {} };
  }
  try {
    return JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
  } catch (e) {
    log.error(`Erro lendo queue: ${e.message}`);
    return { queue: [], in_progress: {}, completed: {}, failed: {} };
  }
}

function saveQueue(data) {
  const tmp = QUEUE_PATH + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), 'utf-8');
  fs.renameSync(tmp, QUEUE_PATH);
}

// Reservas em memoria para evitar que workers peguem o mesmo item antes do saveQueue
const reservedPending = new Set();
const reservedReady = new Set();

function isReady(item) {
  return item.status === 'ready' && (item.sources || []).some(s => s.url);
}

function canRetry(item) {
  const retries = item.retry_count || 0;
  if (retries >= MAX_RETRY) return false;
  const lastFail = item.last_failed ? new Date(item.last_failed).getTime() : 0;
  const delay = Math.min(RETRY_DELAY_MIN * Math.pow(2, retries), 24 * 60 * 60 * 1000);
  return Date.now() - lastFail >= delay;
}

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
  saveQueue(q);
  log.info(`Adicionado: ${serial}`);
  res.json({ added: true, item });
});

app.post('/pause', (req, res) => { paused = true; log.info('Queue paused'); res.json({ paused }); });
app.post('/resume', (req, res) => { paused = false; log.info('Queue resumed'); res.json({ paused }); });

// Cache em memoria da fila para evitar leitura/escrita a cada requisicao
let queueCache = null;
let queueDirty = false;

function getQueue() {
  if (!queueCache) queueCache = loadQueue();
  return queueCache;
}

function markDirty() {
  queueDirty = true;
}

function persistQueue() {
  if (queueDirty && queueCache) {
    saveQueue(queueCache);
    queueDirty = false;
  }
}

setInterval(persistQueue, 30000);

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
  const q = getQueue();
  const ready = q.queue
    .filter(i => i.status === 'ready' && isReady(i) && !reservedReady.has(i.serial) && !q.in_progress[i.serial] && !q.completed[i.serial])
    .sort((a, b) => (b.priority || 0) - (a.priority || 0));
  if (!ready.length) return res.json({ item: null });
  const item = ready[0];
  reservedReady.add(item.serial);
  item.status = 'downloading';
  item.download_started = new Date().toISOString();
  q.in_progress[item.serial] = item;
  markDirty();
  reservedReady.delete(item.serial);
  log.info(`Next ready: ${item.serial}`);
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
  saveQueue(q);
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
  saveQueue(q);
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
    q.failed[serial] = q.in_progress[serial];
    delete q.in_progress[serial];
  }
  // Move item para o fim da fila para nao bloquear outros
  const idx = q.queue.findIndex(i => i.serial === serial);
  if (idx !== -1) {
    const [failedItem] = q.queue.splice(idx, 1);
    q.queue.push(failedItem);
  }
  saveQueue(q);
  log.warn(`Falhou: ${serial} - ${reason} (retry ${item?.retry_count || 0}) -> movido para o fim da fila`);
  res.json({ ok: true });
});

app.post('/reprocess-failures', (req, res) => {
  const q = getQueue();
  let moved = 0;
  // Itens na fila que ainda estao marcados como falha em q.failed
  for (const serial of Object.keys(q.failed || {})) {
    const item = q.queue.find(i => i.serial === serial);
    if (item) {
      item.retry_count = 0;
      item.last_error = null;
      item.last_failed = null;
      item.status = 'pending';
    } else {
      // Item so existe em q.failed; recria na fila
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
  // Tambem reseta itens na fila que ficaram pendurados com status inesperado
  for (const item of q.queue) {
    if (!['pending', 'completed', 'searching', 'downloading', 'ready'].includes(item.status)) {
      item.status = 'pending';
      item.retry_count = 0;
      item.last_error = null;
      item.last_failed = null;
      moved++;
    }
  }
  // Colocar todos os pendentes no fim da fila mantendo ordem relativa
  const nonPending = q.queue.filter(i => i.status !== 'pending');
  const pending = q.queue.filter(i => i.status === 'pending');
  q.queue = [...nonPending, ...pending];
  saveQueue(q);
  log.info(`Reprocessar falhas: ${moved} itens resetados e movidos para o fim da fila`);
  res.json({ ok: true, moved });
});

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
          delete q.in_progress[item.serial];
          drained++;
        }
      }
      if (item.status === 'searching' && item.search_started) {
        const start = new Date(item.search_started).getTime();
        if (now - start > STUCK_SEARCH_MS) {
          item.status = 'pending';
          item.stuck_released = new Date().toISOString();
          delete q.in_progress[item.serial];
          drained++;
        }
      }
    }
    if (drained) {
      saveQueue(q);
      log.warn(`Queue drain: ${drained} itens presos liberados`);
    }
  }, 60000);
}

process.on('uncaughtException', (e) => { console.error('uncaughtException', e.stack || e.message); log.error(`uncaught: ${e.message}`); process.exit(1); });
process.on('unhandledRejection', (e) => { console.error('unhandledRejection', e.stack || e.message); log.error(`rejection: ${e.message}`); });

app.listen(PORTS.QUEUE, '127.0.0.1', () => {
  log.info(`Queue service em http://127.0.0.1:${PORTS.QUEUE}`);
  startQueueDrainWatchdog();
});
