#!/usr/bin/env node
// Processa D:\roms\duplicados — TUDO em F: (SSD), só .chd pronto vai pra D:
// Pipeline: 1 copiador D:->F: + 12 conversores em F: em paralelo
//   1. copiador: copia bin+cue D: -> F:\work (sequencial, max throughput D:)
//   2. conversor: chdman le F:\work, escreve F:\chd_temp (12 em paralelo)
//   3. move .chd F: -> D:\roms\library\roms\psx, deleta bin F:\work

const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');

const DUP_DIR = 'D:\\roms\\duplicados';
const ROM_DIR = 'D:\\roms\\library\\roms\\psx';
const WORK_DIR = 'F:\\work';
const CHD_TEMP = 'F:\\chd_temp';
const CHDMAN = 'F:\\importre\\chdman.exe';
const MAX_CONVERTERS = 12;
const QUEUE_SIZE = MAX_CONVERTERS + 4; // buffer de bins copiados aguardando conversao

for (const d of [WORK_DIR, CHD_TEMP]) {
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
}

const mainChds = new Set(fs.readdirSync(ROM_DIR)
  .filter(f => f.toLowerCase().endsWith('.chd'))
  .map(f => f.replace(/\.chd$/i, '')));

function extractSerial(name) {
  const m = name.match(/(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}/i);
  if (!m) return null;
  return m[0].toUpperCase().replace('_', '-')
    .replace(/^(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)0*(\d{3,5})$/i, '$1-$2');
}

function walkDir(dir) {
  const r = [];
  try {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const f = path.join(dir, e.name);
      if (e.isDirectory()) r.push(...walkDir(f));
      else r.push(f);
    }
  } catch {}
  return r;
}

const allFiles = walkDir(DUP_DIR);
console.log(`Total arquivos: ${allFiles.length} | CHDs colecao: ${mainChds.size}`);

// 1. CHDs soltos -> mover/deletar
const chds = allFiles.filter(f => f.toLowerCase().endsWith('.chd'));
let chdMoved = 0, chdDeleted = 0;
for (const chd of chds) {
  const base = path.basename(chd, '.chd');
  if (mainChds.has(base)) {
    try { fs.unlinkSync(chd); chdDeleted++; } catch {}
  } else {
    try { fs.copyFileSync(chd, path.join(ROM_DIR, path.basename(chd))); fs.unlinkSync(chd); chdMoved++; mainChds.add(base); } catch {}
  }
}
console.log(`CHDs soltos: movidos=${chdMoved} deletados=${chdDeleted}`);

// 2. Construir jobs por BIN
const bins = allFiles.filter(f => /\.(bin|img|iso)$/i.test(f));
const jobs = [];
let skipped = 0;
for (const binPath of bins) {
  try { if (fs.statSync(binPath).size < 1024 * 1024) { skipped++; continue; } } catch { skipped++; continue; }
  const dir = path.dirname(binPath);
  const binExt = path.extname(binPath).toLowerCase();
  const binBase = path.basename(binPath, binExt);
  const serial = extractSerial(path.basename(dir)) || extractSerial(binBase);
  // Nome CHD = nome do bin (sem ext), limpo
  let chdName = `${binBase}.chd`;
  // Se tem serial e o nome do bin nao tem serial, usar serial
  if (serial && !extractSerial(binBase)) chdName = `${serial}.chd`;
  if (mainChds.has(chdName.replace(/\.chd$/i, ''))) { skipped++; continue; }

  const cuePath = path.join(dir, binBase + '.cue');
  if (!fs.existsSync(cuePath)) {
    try { fs.writeFileSync(cuePath, `FILE "${path.basename(binPath)}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`); } catch {}
  }
  jobs.push({ binPath, cuePath, dir, chdName, binBase, binExt });
}
console.log(`Jobs: ${jobs.length} | Skipped: ${skipped}`);
console.log(`Pipeline: 1 copiador D:->F: + ${MAX_CONVERTERS} conversores em F:\n`);

function runChdman(cuePath, chdTempPath) {
  return new Promise((resolve, reject) => {
    execFile(CHDMAN, ['createcd', '-i', cuePath, '-o', chdTempPath, '-c', 'none', '-f'],
      { timeout: 600000, maxBuffer: 1024 * 1024 }, (err) => err ? reject(err) : resolve());
  });
}

// Pipeline com fila
const queue = [];
let queueDone = false;
let copyIdx = 0;
let converted = 0, failed = 0;
const t0 = Date.now();

// Copiador: 1 thread, copia bins de D: -> F: sequencialmente
async function copier() {
  while (copyIdx < jobs.length) {
    // Aguardar vaga na fila
    while (queue.length >= QUEUE_SIZE) {
      await new Promise(r => setTimeout(r, 100));
    }
    if (copyIdx >= jobs.length) break;
    const job = jobs[copyIdx++];
    const safeName = `w${copyIdx}`;
    const workBin = path.join(WORK_DIR, `${safeName}${job.binExt}`);
    const workCue = path.join(WORK_DIR, `${safeName}.cue`);

    try {
      fs.copyFileSync(job.binPath, workBin);
      let cueContent = fs.readFileSync(job.cuePath, 'utf8');
      cueContent = cueContent.replace(/FILE\s+"[^"]+"\s+BINARY/i, `FILE "${safeName}${job.binExt}" BINARY`);
      fs.writeFileSync(workCue, cueContent);
      queue.push({ ...job, workBin, workCue, safeName });
    } catch (e) {
      console.log(`[COPY_ERR] ${job.chdName}: ${e.message.substring(0, 80)}`);
      failed++;
    }
  }
  queueDone = true;
}

// Conversores: 12 workers, pegam bins da fila e convertem em F:
async function converter(id) {
  while (true) {
    let job = null;
    while (!job && !queueDone) {
      if (queue.length > 0) job = queue.shift();
      else await new Promise(r => setTimeout(r, 50));
    }
    if (!job && queueDone && queue.length === 0) break;
    if (!job) continue;

    const { chdName, workBin, workCue, safeName, dir } = job;
    const chdTempPath = path.join(CHD_TEMP, chdName);
    const chdFinalPath = path.join(ROM_DIR, chdName);

    try {
      await runChdman(workCue, chdTempPath);
      if (fs.existsSync(chdTempPath) && fs.statSync(chdTempPath).size > 0) {
        fs.copyFileSync(chdTempPath, chdFinalPath);
        fs.unlinkSync(chdTempPath);
        const sizeMB = (fs.statSync(chdFinalPath).size / 1048576).toFixed(0);
        console.log(`[OK] ${chdName} (${sizeMB}MB)`);
        mainChds.add(chdName.replace(/\.chd$/i, ''));
        converted++;
      } else {
        console.log(`[FAIL] ${chdName}`);
        try { fs.unlinkSync(chdTempPath); } catch {}
        failed++;
      }
    } catch (e) {
      console.log(`[ERROR] ${chdName}: ${e.message.substring(0, 80)}`);
      try { fs.unlinkSync(chdTempPath); } catch {}
      failed++;
    } finally {
      try { fs.unlinkSync(workBin); } catch {}
      try { fs.unlinkSync(workCue); } catch {}
    }

    if ((converted + failed) % 50 === 0) {
      const el = ((Date.now() - t0) / 1000).toFixed(0);
      console.log(`--- ${converted + failed}/${jobs.length} (${converted} ok, ${failed} fail) em ${el}s | fila=${queue.length} ---`);
    }
  }
}

(async () => {
  // Iniciar copiador + conversores
  const copierP = copier();
  const converters = [];
  for (let i = 0; i < MAX_CONVERTERS; i++) converters.push(converter(i));
  await Promise.all([copierP, ...converters]);

  const el = ((Date.now() - t0) / 1000).toFixed(0);
  console.log(`\n=== Resumo ===`);
  console.log(`Convertidos: ${converted}`);
  console.log(`Falhas: ${failed}`);
  console.log(`Tempo: ${el}s`);

  // Limpar D:\roms\duplicados
  console.log('\nLimpando D:\\roms\\duplicados...');
  let cleaned = 0;
  for (const f of walkDir(DUP_DIR)) { try { fs.unlinkSync(f); cleaned++; } catch {} }
  try { for (const e of fs.readdirSync(DUP_DIR, { withFileTypes: true })) if (e.isDirectory()) fs.rmSync(path.join(DUP_DIR, e.name), { recursive: true, force: true }); } catch {}
  console.log(`Limpos: ${cleaned}`);
  console.log(`CHDs finais: ${fs.readdirSync(ROM_DIR).filter(f => f.toLowerCase().endsWith('.chd')).length}`);
})();
