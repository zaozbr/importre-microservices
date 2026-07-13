const express = require('express');
const fs = require('fs');
const path = require('path');
const { spawn, execSync } = require('child_process');
const { PSX_DIR, CHDMAN_PATH, CHD_TEMP_DIR, PORTS, WORKERS } = require('../../shared/config');
const Logger = require('../../shared/logger');

const log = new Logger('chd-service');
const app = express();
app.use(express.json());
app.use('/shared', express.static(path.join(__dirname, '..', '..', 'shared')));

let status = { 
  ready: 0, 
  converting: [], 
  completed: 0, 
  failed: 0, 
  extracting: 0,
  cleaning: 0,
  lastError: null 
};
let running = false;

function extractSerial(name) {
  const m = name.match(/([A-Z]{2,4}[-]\d{3,5})/i);
  return m ? m[1].toUpperCase() : null;
}

function buildChdName(cuePath) {
  const stem = path.basename(cuePath, path.extname(cuePath));
  const serial = extractSerial(stem);
  let base = stem
    .replace(/\(Track \d+\)/gi, '')
    .replace(/\(Disc \d+\)/gi, '')
    .replace(/\(.*?\)/g, '')
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .trim();
  if (serial) base = `${base}-${serial}`;
  return base.slice(0, 180).replace(/[.\s]+$/, '') + '.chd';
}

// Extrai .7z/.zip/.rar para PSX_DIR
function extractArchive(archPath) {
  return new Promise((resolve, reject) => {
    const sevenZip = process.env.SEVEN_ZIP_PATH || 'C:\\Program Files\\7-Zip\\7z.exe';
    const args = ['x', '-y', `-o${PSX_DIR}`, archPath];
    const proc = spawn(sevenZip, args, { windowsHide: true });
    let stderr = '';
    proc.stderr.on('data', d => stderr += d.toString());
    proc.on('exit', (code) => {
      if (code === 0) {
        // Apaga o archive apos extrair
        try { fs.unlinkSync(archPath); } catch (e) {}
        resolve();
      } else {
        reject(new Error(`7z exit ${code}: ${stderr.slice(0, 200)}`));
      }
    });
    proc.on('error', reject);
  });
}

// Encontra arquivos .cue com .bin correspondente, sem .chd ja convertido
function findConversionJobs() {
  const jobs = [];
  const files = fs.readdirSync(PSX_DIR);
  for (const cue of files) {
    if (!cue.toLowerCase().endsWith('.cue')) continue;
    if (cue.toLowerCase().includes('nao-conversivel')) continue;
    const cuePath = path.join(PSX_DIR, cue);
    const chdName = buildChdName(cuePath);
    const chdPath = path.join(PSX_DIR, chdName);
    // Se .chd ja existe e e valido, pula
    if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1024 * 1024) continue;
    
    // Verifica se os .bin referenciados existem
    try {
      const cueContent = fs.readFileSync(cuePath, 'utf-8');
      const refs = [...cueContent.matchAll(/FILE\s+"([^"]+)"/g)].map(m => m[1]);
      const hasBins = refs.every(r => fs.existsSync(path.join(PSX_DIR, r)));
      if (!hasBins) continue;
      jobs.push({ cuePath, chdPath, chdName, binRefs: refs });
    } catch (e) {
      continue;
    }
  }
  return jobs;
}

// Encontra .bin sem .cue mas que podem ser convertidos (gera CUE temporario)
function findOrphanBins() {
  const files = fs.readdirSync(PSX_DIR);
  const cueStems = new Set(
    files.filter(f => f.toLowerCase().endsWith('.cue'))
         .map(f => f.replace(/\.cue$/i, ''))
  );
  const orphans = [];
  for (const f of files) {
    if (!f.toLowerCase().endsWith('.bin')) continue;
    const stem = f.replace(/\.bin$/i, '');
    if (cueStems.has(stem)) continue; // tem .cue correspondente
    // .bin unico (sem tracks) - pode gerar CUE
    const binPath = path.join(PSX_DIR, f);
    const st = fs.statSync(binPath);
    if (st.size < 1024 * 1024) continue; // muito pequeno
    orphans.push({ binPath, binName: f, stem });
  }
  return orphans;
}

function convertOne(job) {
  return new Promise((resolve) => {
    log.info(`Convertendo ${job.chdName}`);
    status.converting.push(job.chdName);
    const proc = spawn(CHDMAN_PATH, ['createcd', '-i', job.cuePath, '-o', job.chdPath, '-f'], { cwd: PSX_DIR });
    let stderr = '';
    proc.stderr.on('data', d => stderr += d.toString());
    proc.on('exit', (code) => {
      status.converting = status.converting.filter(n => n !== job.chdName);
      const ok = fs.existsSync(job.chdPath) && fs.statSync(job.chdPath).size > 1024 * 1024;
      if (ok) {
        log.info(`OK ${job.chdName} (${Math.round(fs.statSync(job.chdPath).size / 1024)}KB)`);
        status.completed++;
        // Apaga .bin e .cue apos conversao bem-sucedida
        cleanupAfterConversion(job);
      } else {
        log.error(`Falha ${job.chdName}: ${stderr.slice(0, 200)}`);
        status.failed++;
        status.lastError = `${job.chdName}: ${stderr.slice(0, 200)}`;
        // Apaga .chd incompleto
        try { fs.unlinkSync(job.chdPath); } catch (e) {}
      }
      resolve();
    });
    proc.on('error', (e) => {
      status.converting = status.converting.filter(n => n !== job.chdName);
      status.failed++;
      status.lastError = e.message;
      log.error(`Erro spawn chdman: ${e.message}`);
      resolve();
    });
  });
}

// Apaga .bin e .cue apos conversao .chd bem-sucedida
function cleanupAfterConversion(job) {
  try {
    // Apaga .bin referenciados
    for (const ref of job.binRefs) {
      const binPath = path.join(PSX_DIR, ref);
      if (fs.existsSync(binPath)) {
        fs.unlinkSync(binPath);
        log.info(`Apagado ${ref} (convertido para .chd)`);
      }
    }
    // Apaga .cue
    if (fs.existsSync(job.cuePath)) {
      fs.unlinkSync(job.cuePath);
      log.info(`Apagado ${path.basename(job.cuePath)} (convertido para .chd)`);
    }
  } catch (e) {
    log.warn(`Erro ao limpar apos conversao: ${e.message}`);
  }
}

// Gera CUE temporario para .bin orfao e converte
function convertOrphanBin(orphan) {
  return new Promise((resolve) => {
    const tmpCue = path.join(PSX_DIR, orphan.stem + '.cue');
    const cueContent = `FILE "${orphan.binName}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`;
    try {
      fs.writeFileSync(tmpCue, cueContent);
    } catch (e) {
      return resolve();
    }
    const chdName = buildChdName(tmpCue);
    const chdPath = path.join(PSX_DIR, chdName);
    if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1024 * 1024) {
      // Ja convertido, apaga .bin e .cue
      fs.unlinkSync(orphan.binPath);
      fs.unlinkSync(tmpCue);
      return resolve();
    }
    const job = { cuePath: tmpCue, chdPath, chdName, binRefs: [orphan.binName] };
    convertOne(job).then(resolve);
  });
}

async function loop() {
  running = true;
  while (running) {
    try {
      // 1. Extrai arquivos .7z/.zip/.rar pendentes
      const archives = fs.readdirSync(PSX_DIR)
        .filter(f => /\.(7z|zip|rar)$/i.test(f))
        .map(f => path.join(PSX_DIR, f));
      if (archives.length > 0) {
        status.extracting = archives.length;
        log.info(`Extraindo ${archives.length} arquivos compactados...`);
        for (const arch of archives.slice(0, 5)) {
          try {
            await extractArchive(arch);
            log.info(`Extraido: ${path.basename(arch)}`);
          } catch (e) {
            log.warn(`Erro ao extrair ${path.basename(arch)}: ${e.message}`);
            // Apaga archive corrompido
            try { fs.unlinkSync(arch); } catch (e2) {}
          }
        }
        status.extracting = 0;
      }
      
      // 2. Converte .cue + .bin para .chd
      const jobs = findConversionJobs();
      status.ready = jobs.length;
      if (jobs.length > 0) {
        const workers = Math.min(WORKERS.CHD, jobs.length);
        log.info(`Convertendo ${jobs.length} .cue -> .chd (${workers} workers)`);
        await Promise.all(jobs.slice(0, workers).map(convertOne));
      }
      
      // 3. Converte .bin orfaos (sem .cue)
      const orphans = findOrphanBins();
      if (orphans.length > 0 && orphans.length < 50) {
        log.info(`Convertendo ${orphans.length} .bin orfaos...`);
        const workers = Math.min(WORKERS.CHD, orphans.length);
        await Promise.all(orphans.slice(0, workers).map(convertOrphanBin));
      }
      
    } catch (e) {
      log.error(`Loop error: ${e.message}`);
    }
    await new Promise(r => setTimeout(r, 10000));
  }
}

app.get('/status', (req, res) => res.json(status));
app.get('/dashboard', (req, res) => res.sendFile(path.join(__dirname, 'dashboard.html')));

process.on('uncaughtException', (e) => log.error(`uncaught: ${e.message}`));
process.on('unhandledRejection', (e) => log.error(`rejection: ${e.message}`));

app.listen(PORTS.CHD, '127.0.0.1', () => {
  log.info(`CHD service em http://127.0.0.1:${PORTS.CHD}`);
  loop();
});
