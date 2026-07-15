/**
 * Testa CHDs no DuckStation um a um e verifica se o memory card foi criado.
 * Se o memory card nao for criado, o CHD e considerado invalido.
 *
 * Uso: node tools/test_chd_memcard.js
 */
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const DUCK = 'C:\\Users\\Usuario\\AppData\\Local\\Programs\\DuckStation\\duckstation-qt-x64-ReleaseLTCG.exe';
const PSX_DIR = 'D:\\roms\\library\\roms\\psx';
const DUP_DIR = 'D:\\roms\\duplicados';
const DUCK_LOG = 'C:\\Users\\Usuario\\Documents\\DuckStation\\duckstation.log';
const MEMCARD_DIR = 'C:\\Users\\Usuario\\Documents\\DuckStation\\memcards';
const QUEUE_PATH = 'D:\\roms\\library\\roms\\_importre_state\\queue.json';

const CHDS_TO_TEST = [
  'Battle-Arena-Nitoushinden-SLPS-00485.chd',
  'Criticom-The-Critical-Combat-SLPS-00229.chd',
  'Battle-Master-SLPM-86519.chd',
  'Battle-Master-SLPS-01064.chd',
  'Time-Gal-Ninja-Hayate-SLPS-00383.chd',
  'Time-Gal-Ninja-Hayate-SLPS-00384.chd',
  'Chess-2000-Reprint-SLPM-86732.chd',
  'Chess-2000-System-Tal-SLPS-02624.chd',
];

function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function listMemcards() {
  return new Set(fs.readdirSync(MEMCARD_DIR).filter(f => f.endsWith('.mcd')));
}

function clearLog() {
  for (let i = 0; i < 5; i++) {
    try {
      if (fs.existsSync(DUCK_LOG)) fs.unlinkSync(DUCK_LOG);
      return;
    } catch (e) {
      sleep(2000);
    }
  }
}

function extractSerial(chdName) {
  // Battle-Arena-Nitoushinden-SLPS-00485.chd -> SLPS-00485
  const match = chdName.match(/(SLPS|SLES|SLUS|SCPS|SCES|SCUS|SLPM)-(\d{5})/);
  return match ? `${match[1]}-${match[2]}` : null;
}

function moveToDuplicates(chdName) {
  const src = path.join(PSX_DIR, chdName);
  const dst = path.join(DUP_DIR, chdName);
  if (fs.existsSync(src)) {
    fs.renameSync(src, dst);
    console.log(`  -> Movido para D:\\roms\\duplicados\\${chdName}`);
  }
}

function addToQueue(serial, title) {
  const queue = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf8'));
  const existing = queue.queue.find(i => i.serial === serial);
  if (existing) {
    existing.status = 'pending';
    existing.retry_count = 0;
    existing.last_failed = null;
    existing.last_error = null;
    existing.sources = [];
    existing.site_history = {};
    delete existing.completed;
    delete existing.download_started;
    delete existing.search_started;
    delete existing.search_ended;
    delete existing.stuck_released;
    delete existing.cooldown_until;
    console.log(`  -> Fila: ${serial} resetado para pending`);
  } else {
    queue.queue.push({
      serial,
      title,
      status: 'pending',
      priority: 1,
      added: new Date().toISOString(),
      retry_count: 0,
      site_history: {},
      sources: [],
    });
    console.log(`  -> Fila: ${serial} adicionado como pending`);
  }
  fs.writeFileSync(QUEUE_PATH, JSON.stringify(queue, null, 2));
}

function testChd(chdName) {
  const chdPath = path.join(PSX_DIR, chdName);
  if (!fs.existsSync(chdPath)) {
    return { chd: chdName, status: 'NOT_FOUND', memcardCreated: false };
  }

  // Snapshot dos memory cards antes
  const memcardsBefore = listMemcards();

  // Limpar log
  clearLog();

  console.log(`  Testando: ${chdName}...`);

  let proc;
  try {
    proc = execSync(`"${DUCK}" -batch -fastboot -earlyconsole -- "${chdPath}"`, {
      stdio: 'pipe',
      timeout: 40000,
    });
  } catch (e) {
    // Timeout esperado
  }

  // Esperar processo terminar
  sleep(3000);

  // Snapshot dos memory cards depois
  const memcardsAfter = listMemcards();

  // Verificar se algum memory card novo foi criado
  const newMemcards = [...memcardsAfter].filter(m => !memcardsBefore.has(m));

  // Ler log
  const log = fs.existsSync(DUCK_LOG) ? fs.readFileSync(DUCK_LOG, 'utf8') : '';
  const hasBoot = log.includes('System booted');
  const hasRegion = log.match(/Auto-detected console (\S+) region/);
  const region = hasRegion ? hasRegion[1] : 'unknown';
  const hasNonPS1 = log.includes('Non-PS1');
  const hasMemcardLine = log.includes('Memory Card 1:');

  const memcardCreated = newMemcards.length > 0 || hasMemcardLine;

  let status;
  if (hasBoot && memcardCreated) status = 'OK';
  else if (hasNonPS1) status = 'NON-PS1';
  else if (!hasBoot) status = 'NO_BOOT';
  else if (!memcardCreated) status = 'NO_MEMCARD';
  else status = 'UNKNOWN';

  return {
    chd: chdName,
    status,
    region,
    memcardCreated,
    newMemcards,
    hasBoot,
    hasNonPS1,
  };
}

// === Main ===
console.log('=== Teste de CHDs no DuckStation (verificacao de memory card) ===\n');

const results = [];
const failed = [];

for (const chd of CHDS_TO_TEST) {
  const result = testChd(chd);
  results.push(result);

  const memcardInfo = result.newMemcards.length > 0
    ? `memcard: ${result.newMemcards.join(', ')}`
    : `memcard: ${result.memcardCreated ? 'sim (existente)' : 'NAO'}`;

  console.log(`  -> ${result.status} | regiao: ${result.region} | ${memcardInfo}`);

  if (result.status !== 'OK') {
    failed.push(result);
  }
}

console.log('\n=== Resultado ===');
console.log('CHD'.padEnd(50) + 'Status'.padEnd(12) + 'Regiao'.padEnd(10) + 'Memcard');
console.log('-'.repeat(95));
for (const r of results) {
  console.log(
    r.chd.padEnd(50) +
    r.status.padEnd(12) +
    r.region.padEnd(10) +
    (r.memcardCreated ? 'sim' : 'NAO')
  );
}

// Processar falhas
if (failed.length > 0) {
  console.log(`\n=== Processando ${failed.length} falhas ===`);
  for (const f of failed) {
    console.log(`\n${f.chd}: ${f.status}`);
    const serial = extractSerial(f.chd);
    if (serial) {
      moveToDuplicates(f.chd);
      addToQueue(serial, f.chd.replace(/\.chd$/, '').replace(/-/g, ' '));
    } else {
      console.log(`  -> AVISO: serial nao encontrado no nome, nao foi possivel rebaixar`);
    }
  }
} else {
  console.log('\nTodos os CHDs passaram no teste!');
}
