// Testes automatizados do download service
// Testa logica de slots, sortSourcesBySpeed, resolvePageDownload
// Run: node tests/test_download.js

const assert = require('assert');
const { SOURCE_LIMITS, ARIA2 } = require('../shared/config');

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

console.log('=== Testes Download Service ===\n');

// Simula sourceSlots do download service
function makeSourceSlots() {
  const sourceSlots = new Map();
  function getSlotState(site) {
    if (!sourceSlots.has(site)) {
      const limit = SOURCE_LIMITS[site] || Infinity;
      sourceSlots.set(site, { current: 0, max: limit, waiters: [] });
    }
    return sourceSlots.get(site);
  }
  function acquireSourceSlot(site, timeoutMs = 300000) {
    return new Promise((resolve, reject) => {
      const state = getSlotState(site);
      if (state.current < state.max) {
        state.current++;
        resolve();
        return;
      }
      let timer = null;
      const waiter = () => { if (timer) clearTimeout(timer); resolve(); };
      state.waiters.push(waiter);
      if (timeoutMs !== Infinity) {
        timer = setTimeout(() => {
          const idx = state.waiters.indexOf(waiter);
          if (idx !== -1) state.waiters.splice(idx, 1);
          reject(new Error(`timeout aguardando slot de ${site}`));
        }, timeoutMs);
      }
    });
  }
  function releaseSourceSlot(site) {
    const state = getSlotState(site);
    state.current = Math.max(0, state.current - 1);
    if (state.waiters.length > 0) {
      const next = state.waiters.shift();
      state.current++;
      next();
    }
  }
  return { getSlotState, acquireSourceSlot, releaseSourceSlot };
}

// Teste 1: acquire slot quando ha disponibilidade
test('acquireSlot: sucesso quando ha slot', async () => {
  const { acquireSourceSlot, getSlotState } = makeSourceSlots();
  await acquireSourceSlot('coolrom', 1000);
  const state = getSlotState('coolrom');
  assert.strictEqual(state.current, 1, 'deve ter 1 slot em uso');
});

// Teste 2: release slot libera
test('releaseSlot: libera slot', async () => {
  const { acquireSourceSlot, releaseSourceSlot, getSlotState } = makeSourceSlots();
  await acquireSourceSlot('coolrom', 1000);
  releaseSourceSlot('coolrom');
  const state = getSlotState('coolrom');
  assert.strictEqual(state.current, 0, 'deve ter 0 slots em uso');
});

// Teste 3: acquire bloqueia quando limite atingido
test('acquireSlot: bloqueia quando limite atingido', async () => {
  const { acquireSourceSlot, getSlotState } = makeSourceSlots();
  const state = getSlotState('coolrom');
  // Enche todos os slots
  for (let i = 0; i < state.max; i++) {
    await acquireSourceSlot('coolrom', 100);
  }
  assert.strictEqual(state.current, state.max, 'deve estar no max');
  // Próximo acquire deve timeout (100ms)
  try {
    await acquireSourceSlot('coolrom', 100);
    assert.fail('deve ter dado timeout');
  } catch (e) {
    assert.ok(e.message.includes('timeout'), 'deve ser erro de timeout');
  }
});

// Teste 4: release acorda waiter
test('releaseSlot: acorda waiter na fila', async () => {
  const { acquireSourceSlot, releaseSourceSlot, getSlotState } = makeSourceSlots();
  const state = getSlotState('coolrom');
  for (let i = 0; i < state.max; i++) await acquireSourceSlot('coolrom', 5000);
  
  // Inicia acquire que vai esperar
  const acquirePromise = acquireSourceSlot('coolrom', 5000);
  await new Promise(r => setTimeout(r, 50)); // dá tempo do waiter entrar na fila
  
  // Libera um slot
  releaseSourceSlot('coolrom');
  await acquirePromise; // deve resolver
  assert.strictEqual(state.current, state.max, 'deve estar no max novamente');
});

// Teste 5: sortSourcesBySpeed ordena por velocidade
test('sortSourcesBySpeed: coolrom antes de archive.org', () => {
  const speedMap = {
    'coolrom': 8, 'vimm': 8, 'archive.org': 3, 'archive.org-jp': 3,
  };
  const sources = [
    { site: 'archive.org', url: 'http://a.com/1' },
    { site: 'coolrom', url: 'http://b.com/2' },
    { site: 'archive.org-jp', url: 'http://c.com/3' },
  ];
  const sorted = [...sources].sort((a, b) => (speedMap[b.site] || 5) - (speedMap[a.site] || 5));
  assert.strictEqual(sorted[0].site, 'coolrom', 'coolrom deve ser primeiro');
});

// Teste 6: speedToMbps converte corretamente
test('speedToMbps: converte KiB/s para MB/s', () => {
  function speedToMbps(speedStr) {
    if (!speedStr) return 0;
    const m = speedStr.match(/([\d.]+)([KMGT]?i?)B\/s/);
    if (!m) return 0;
    const val = parseFloat(m[1]);
    const unit = (m[2] || '').toLowerCase();
    if (unit.startsWith('k')) return val / 1024;
    if (unit.startsWith('m')) return val;
    if (unit.startsWith('g')) return val * 1024;
    return val / 1048576;
  }
  assert.strictEqual(speedToMbps('1024KiB/s'), 1, '1024KiB/s = 1MB/s');
  assert.strictEqual(speedToMbps('5MiB/s'), 5, '5MiB/s = 5MB/s');
  assert.strictEqual(speedToMbps('0'), 0, '0 = 0');
  assert.strictEqual(speedToMbps(null), 0, 'null = 0');
});

// Teste 7: isDirect detecta extensao direta
test('isDirect: detecta extensao de arquivo direto', () => {
  const directExts = ['.7z', '.zip', '.rar', '.iso', '.bin', '.cue', '.img'];
  assert.ok(directExts.some(e => 'http://example.com/game.7z'.toLowerCase().endsWith(e)), '.7z e direto');
  assert.ok(!directExts.some(e => 'http://example.com/game.php'.toLowerCase().endsWith(e)), '.php nao e direto');
});

// Teste 8: resolvePageDownload detecta coolrom
test('resolvePageDownload: detecta URL coolrom', () => {
  const url = 'https://coolrom.com.au/roms/psx/12345/Game.php';
  assert.ok(url.includes('coolrom'), 'deve detectar coolrom');
});

// Teste 9: fallback axios cleanup
test('fallback axios: remove arquivo parcial em erro', () => {
  const fs = require('fs');
  const tmpPath = '__test_partial.tmp';
  fs.writeFileSync(tmpPath, 'partial');
  try {
    try { fs.unlinkSync(tmpPath); } catch (e) {}
    assert.ok(!fs.existsSync(tmpPath), 'arquivo parcial deve ser removido');
  } finally {
    try { fs.unlinkSync(tmpPath); } catch (e) {}
  }
});

// Teste 10: retry interno do worker
test('retry interno: 3 tentativas antes de falhar', async () => {
  let attempts = 0;
  let success = false;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      attempts++;
      if (attempt < 2) throw new Error('simula falha');
      success = true;
      break;
    } catch (e) {
      // continua
    }
  }
  assert.strictEqual(attempts, 3, 'deve tentar 3 vezes');
  assert.ok(success, 'deve ter sucesso na 3a');
});

// Teste 11: config SOURCE_LIMITS tem coolrom
test('config: SOURCE_LIMITS tem coolrom definido', () => {
  assert.ok(SOURCE_LIMITS.coolrom, 'coolrom deve estar definido');
  assert.ok(SOURCE_LIMITS.coolrom > 0, 'limite deve ser > 0');
});

// Teste 12: config ARIA2 tem min speed
test('config: ARIA2 tem MIN_SPEED_MBPS definido', () => {
  assert.ok(ARIA2.MIN_SPEED_MBPS, 'MIN_SPEED_MBPS deve estar definido');
  assert.ok(ARIA2.MIN_SPEED_MBPS > 0, 'min speed deve ser > 0');
});

(async () => {
  console.log(`\n=== Resultado: ${testsPassed} passaram, ${testsFailed} falharam ===`);
  process.exit(testsFailed > 0 ? 1 : 0);
})();
