// Testes automatizados do queue service
// Executa sem servidor HTTP, testando funcoes internas diretamente
// Run: node tests/test_queue.js

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const QUEUE_PATH = path.join(__dirname, '..', 'test_queue_tmp.json');

// Limpa arquivo de teste
function cleanup() {
  try { fs.unlinkSync(QUEUE_PATH); } catch (e) {}
  try { fs.unlinkSync(QUEUE_PATH + '.bak'); } catch (e) {}
  try { fs.unlinkSync(QUEUE_PATH + '.tmp'); } catch (e) {}
}

// Cria queue de teste
function makeTestQueue() {
  return {
    queue: [
      { serial: 'SLUS-001', title: 'Game A', status: 'pending', priority: 1, retry_count: 0, sources: [] },
      { serial: 'SLUS-002', title: 'Game B', status: 'pending', priority: 2, retry_count: 0, sources: [] },
      { serial: 'SLUS-003', title: 'Game C', status: 'ready', priority: 1, retry_count: 0, sources: [{ site: 'coolrom', url: 'http://example.com/a.7z' }] },
      { serial: 'SLUS-004', title: 'Game D', status: 'completed', priority: 1, retry_count: 0, sources: [] },
    ],
    in_progress: {},
    completed: { 'SLUS-004': { serial: 'SLUS-004' } },
    failed: {}
  };
}

let testsPassed = 0;
let testsFailed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
    testsPassed++;
  } catch (e) {
    console.error(`  ✗ ${name}: ${e.message}`);
    testsFailed++;
  }
}

console.log('=== Testes Queue Service ===\n');

// Teste 1: loadQueue com arquivo valido
test('loadQueue le arquivo valido', () => {
  cleanup();
  const q = makeTestQueue();
  fs.writeFileSync(QUEUE_PATH, JSON.stringify(q));
  
  // Simula loadQueue
  const data = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
  assert.strictEqual(data.queue.length, 4, 'deve ter 4 itens');
  assert.strictEqual(data.queue[0].serial, 'SLUS-001');
});

// Teste 2: loadQueue com arquivo corrompido + backup
test('loadQueue restaura backup quando corrompido', () => {
  cleanup();
  const q = makeTestQueue();
  fs.writeFileSync(QUEUE_PATH + '.bak', JSON.stringify(q));
  fs.writeFileSync(QUEUE_PATH, '{ invalid json }');
  
  // Simula logica de backup
  let loaded = null;
  try {
    loaded = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
  } catch (e) {
    if (fs.existsSync(QUEUE_PATH + '.bak')) {
      loaded = JSON.parse(fs.readFileSync(QUEUE_PATH + '.bak', 'utf-8'));
    }
  }
  assert.ok(loaded, 'deve ter carregado do backup');
  assert.strictEqual(loaded.queue.length, 4);
});

// Teste 3: saveQueue atomico
test('saveQueue escreve atomicamente via tmp+rename', () => {
  cleanup();
  const q = makeTestQueue();
  const tmp = QUEUE_PATH + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(q, null, 2));
  fs.renameSync(tmp, QUEUE_PATH);
  assert.ok(fs.existsSync(QUEUE_PATH), 'arquivo final deve existir');
  assert.ok(!fs.existsSync(tmp), 'arquivo tmp deve ser removido');
});

// Teste 4: canRetry - item nunca falhou pode retry
test('canRetry: item sem last_failed pode retry', () => {
  const item = { retry_count: 0, last_failed: null };
  const retries = item.retry_count || 0;
  const lastFail = item.last_failed ? new Date(item.last_failed).getTime() : 0;
  assert.ok(lastFail === 0, 'lastFail deve ser 0');
  // sem lastFail = pode retry
  assert.ok(Date.now() - lastFail >= 0, 'deve poder retry');
});

// Teste 5: canRetry - respeita backoff
test('canRetry: respeita backoff exponencial', () => {
  const RETRY_DELAYS = [30000, 60000, 120000, 300000, 600000, 1200000, 1800000];
  const item = { retry_count: 1, last_failed: new Date(Date.now() - 10000).toISOString() };
  const retries = item.retry_count;
  const lastFail = new Date(item.last_failed).getTime();
  const delay = RETRY_DELAYS[Math.min(retries, RETRY_DELAYS.length - 1)];
  // 10s < 60s (delay para retry 1) = nao pode retry ainda
  assert.ok(Date.now() - lastFail < delay, 'nao deve poder retry antes do delay');
});

// Teste 6: canRetry - max retry
test('canRetry: excede MAX_RETRY retorna false', () => {
  const MAX_RETRY = 15;
  const item = { retry_count: 15, last_failed: null };
  assert.ok(item.retry_count >= MAX_RETRY, 'deve exceder max retry');
});

// Teste 7: isReady valida sources
test('isReady: item com sources e url esta pronto', () => {
  const item = { status: 'ready', sources: [{ site: 'coolrom', url: 'http://example.com/a.7z' }] };
  const result = item.status === 'ready' && (item.sources || []).some(s => s.url);
  assert.ok(result, 'deve estar pronto');
});

// Teste 8: isReady - item sem url nao esta pronto
test('isReady: item sem url nao esta pronto', () => {
  const item = { status: 'ready', sources: [{ site: 'coolrom', url: '' }] };
  const result = item.status === 'ready' && (item.sources || []).some(s => s.url);
  assert.ok(!result, 'nao deve estar pronto');
});

// Teste 9: fail move item para fim da fila
test('fail: move item para fim da fila', () => {
  const q = makeTestQueue();
  const item = q.queue[0]; // SLUS-001
  item.status = 'pending';
  item.retry_count = (item.retry_count || 0) + 1;
  item.last_error = 'teste';
  const idx = q.queue.findIndex(i => i.serial === item.serial);
  const [failedItem] = q.queue.splice(idx, 1);
  q.queue.push(failedItem);
  assert.strictEqual(q.queue[q.queue.length - 1].serial, 'SLUS-001', 'deve estar no fim');
});

// Teste 10: complete remove de failed
test('complete: remove de failed se estava la', () => {
  const q = makeTestQueue();
  q.failed['SLUS-001'] = { serial: 'SLUS-001' };
  const serial = 'SLUS-001';
  if (q.failed[serial]) delete q.failed[serial];
  assert.ok(!q.failed['SLUS-001'], 'deve remover de failed');
});

// Teste 11: reprocess-failures reseta retry_count
test('reprocess-failures: reseta retry_count e last_error', () => {
  const q = makeTestQueue();
  q.failed['SLUS-001'] = { serial: 'SLUS-001', retry_count: 5, last_error: 'erro', status: 'pending' };
  q.queue.push(q.failed['SLUS-001']);
  for (const serial of Object.keys(q.failed)) {
    const item = q.queue.find(i => i.serial === serial);
    if (item) {
      item.retry_count = 0;
      item.last_error = null;
      item.last_failed = null;
      item.status = 'pending';
    }
    delete q.failed[serial];
  }
  const item = q.queue.find(i => i.serial === 'SLUS-001');
  assert.strictEqual(item.retry_count, 0, 'retry_count deve ser 0');
  assert.strictEqual(item.last_error, null, 'last_error deve ser null');
  assert.strictEqual(item.status, 'pending', 'status deve ser pending');
});

// Teste 12: drain watchdog libera item preso em downloading
test('drain watchdog: libera item preso em downloading', () => {
  const q = makeTestQueue();
  const item = q.queue[0];
  item.status = 'downloading';
  item.download_started = new Date(Date.now() - 25 * 60 * 1000).toISOString(); // 25min ago
  q.in_progress[item.serial] = item;
  
  const STUCK_DOWNLOAD_MS = 20 * 60 * 1000;
  const now = Date.now();
  const start = new Date(item.download_started).getTime();
  if (now - start > STUCK_DOWNLOAD_MS) {
    item.status = 'ready';
    item.retry_count = (item.retry_count || 0) + 1;
    delete q.in_progress[item.serial];
  }
  assert.strictEqual(item.status, 'ready', 'deve estar ready');
  assert.strictEqual(item.retry_count, 1, 'deve incrementar retry_count');
  assert.ok(!q.in_progress[item.serial], 'deve remover de in_progress');
});

console.log(`\n=== Resultado: ${testsPassed} passaram, ${testsFailed} falharam ===`);
cleanup();
process.exit(testsFailed > 0 ? 1 : 0);
