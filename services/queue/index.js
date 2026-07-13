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
  fs.writeFileSync(QUEUE_PATH, JSON.stringify(data, null, 2), 'utf-8');
}

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
  const q = loadQueue();
  res.json({
    pending: q.queue.filter(i => i.status === 'pending').length,
    searching: q.queue.filter(i => i.status === 'searching').length,
    ready: q.queue.filter(i => i.status === 'ready').length,
    downloading: q.queue.filter(i => i.status === 'downloading').length,
    in_progress: Object.keys(q.in_progress || {}).length,
    completed: Object.keys(q.completed || {}).length,
    failed: Object.keys(q.failed || {}).length,
    total: q.queue.length
  });
});

app.get('/queue', (req, res) => res.json(loadQueue()));

app.post('/queue/add', (req, res) => {
  const { serial, title, priority = 1 } = req.body;
  if (!serial) return res.status(400).json({ error: 'serial required' });
  const q = loadQueue();
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

// Search service pega um item pending
app.post('/queue/next-pending', (req, res) => {
  const q = loadQueue();
  const pending = q.queue
    .filter(i => i.status === 'pending' && !q.in_progress[i.serial] && !q.completed[i.serial] && canRetry(i))
    .sort((a, b) => (b.priority || 0) - (a.priority || 0));
  if (!pending.length) return res.json({ item: null });
  const item = pending[0];
  item.status = 'searching';
  item.search_started = new Date().toISOString();
  q.in_progress[item.serial] = item;
  saveQueue(q);
  log.info(`Next pending: ${item.serial}`);
  res.json({ item });
});

// Download service pega um item ready
app.post('/queue/next-ready', (req, res) => {
  const q = loadQueue();
  const ready = q.queue
    .filter(i => i.status === 'ready' && isReady(i) && !q.in_progress[i.serial] && !q.completed[i.serial])
    .sort((a, b) => (b.priority || 0) - (a.priority || 0));
  if (!ready.length) return res.json({ item: null });
  const item = ready[0];
  item.status = 'downloading';
  item.download_started = new Date().toISOString();
  q.in_progress[item.serial] = item;
  saveQueue(q);
  log.info(`Next ready: ${item.serial}`);
  res.json({ item });
});

app.post('/queue/ready', (req, res) => {
  const { serial, sources } = req.body;
  const q = loadQueue();
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
  const q = loadQueue();
  const item = q.queue.find(i => i.serial === serial);
  if (!item) return res.status(404).json({ error: 'not found' });
  Object.assign(item, updates);
  if (q.in_progress[serial]) Object.assign(q.in_progress[serial], updates);
  saveQueue(q);
  res.json({ item });
});

app.post('/queue/complete', (req, res) => {
  const { serial } = req.body;
  const q = loadQueue();
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
  const q = loadQueue();
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
  saveQueue(q);
  log.warn(`Falhou: ${serial} - ${reason} (retry ${item?.retry_count || 0})`);
  res.json({ ok: true });
});

process.on('uncaughtException', (e) => log.error(`uncaught: ${e.message}`));
process.on('unhandledRejection', (e) => log.error(`rejection: ${e.message}`));

app.listen(PORTS.QUEUE, () => {
  log.info(`Queue service em http://127.0.0.1:${PORTS.QUEUE}`);
});
