/**
 * batch_chd_convert.js — Conversão em lote de downloads para .chd
 *
 * Lista arquivos .zip/.rar/.7z/.bin em F:\downloads que ainda não têm .chd
 * correspondente em F:\testes, extrai, converte com chdman e move o .chd
 * para F:\testes. Máximo 2 conversões simultâneas.
 *
 * Uso: node batch_chd_convert.js
 */
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const os = require('os');

const DOWNLOAD_DIR = 'F:\\downloads';
const OUTPUT_DIR = 'F:\\testes';
const TEMP_BASE = path.join(os.tmpdir(), 'chd_batch');
const CHDMAN = 'F:\\importre\\chdman.exe';
const SEVEN_ZIP = 'C:\\Program Files\\7-Zip\\7z.exe';
const MAX_CONCURRENT = 2;
const ARCHIVE_EXTS = ['.zip', '.rar', '.7z', '.bin'];

// ── Util ──────────────────────────────────────────────────────────────────

function log(msg) {
  console.log(`[${new Date().toISOString()}] ${msg}`);
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

/** Extrai serial do nome do arquivo (ex: SLUS-00012.1.rar → SLUS-00012) */
function extractSerial(name) {
  const m = name.match(/([A-Z]{2,4}[-]\d{3,5})/i);
  return m ? m[1].toUpperCase() : null;
}

/** Determina o nome do .chd de saída a partir do nome do arquivo de origem */
function buildChdName(fileName) {
  const base = path.basename(fileName, path.extname(fileName));
  const serial = extractSerial(base);
  // Se tem serial, usa o serial + sufixo de disco (ex: .1, .2)
  if (serial) {
    const discMatch = base.match(/\.(\d+)$/);
    const discSuffix = discMatch ? `.${discMatch[1]}` : '';
    return `${serial}${discSuffix}.chd`;
  }
  // Sem serial: sanitiza o nome do arquivo
  const sanitized = base
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 180);
  return `${sanitized}.chd`;
}

/** Verifica se já existe .chd correspondente em F:\testes */
function chdExists(chdName) {
  const chdPath = path.join(OUTPUT_DIR, chdName);
  return fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1024 * 1024;
}

/** Lista arquivos de archive em F:\downloads */
function listArchives() {
  const files = fs.readdirSync(DOWNLOAD_DIR);
  const archives = [];
  const multiPartRars = new Set(); // base names of multi-part RARs already seen

  for (const f of files) {
    const ext = path.extname(f).toLowerCase();
    if (!ARCHIVE_EXTS.includes(ext)) continue;

    const fullPath = path.join(DOWNLOAD_DIR, f);
    let stat;
    try {
      stat = fs.statSync(fullPath);
    } catch { continue; }
    if (!stat.isFile()) continue;
    if (stat.size === 0) {
      log(`  SKIP (0 bytes): ${f}`);
      continue;
    }

    // Pula arquivos .bin muito pequenos (provavelmente não são imagens PSX)
    if (ext === '.bin' && stat.size < 1024 * 1024) {
      log(`  SKIP (muito pequeno): ${f} (${stat.size} bytes)`);
      continue;
    }

    // Para RAR multi-volume (ex: SLUS-00519.2.rar, .3.rar, etc),
    // processa apenas a primeira parte (.rar sem número ou .rar)
    if (ext === '.rar') {
      const partMatch = f.match(/^(.+)\.(\d+)\.rar$/i);
      if (partMatch) {
        const baseName = partMatch[1];
        if (multiPartRars.has(baseName)) {
          // Já vimos a primeira parte, pula esta
          continue;
        }
        // Verifica se a primeira parte (.rar) existe
        const firstPart = `${baseName}.rar`;
        if (fs.existsSync(path.join(DOWNLOAD_DIR, firstPart))) {
          continue; // a primeira parte será processada
        }
        multiPartRars.add(baseName);
      }
    }

    archives.push({ name: f, path: fullPath, size: stat.size, ext });
  }

  return archives;
}

// ── Extração ──────────────────────────────────────────────────────────────

function extractArchive(archPath, destDir) {
  return new Promise((resolve) => {
    const proc = spawn(SEVEN_ZIP, ['x', '-y', `-o${destDir}`, archPath], {
      windowsHide: true,
    });
    let stderr = '';
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => resolve({ success: code === 0, error: stderr }));
    proc.on('error', (e) => resolve({ success: false, error: e.message }));
  });
}

// ── Conversão CHD ─────────────────────────────────────────────────────────

function convertCueToChd(cuePath, chdPath) {
  return new Promise((resolve) => {
    const proc = spawn(CHDMAN, ['createcd', '-i', cuePath, '-o', chdPath, '-f'], {
      cwd: path.dirname(cuePath),
      windowsHide: true,
    });
    let stderr = '';
    let stdout = '';
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => resolve({ success: code === 0, error: stderr, stdout }));
    proc.on('error', (e) => resolve({ success: false, error: e.message }));
  });
}

function generateCueForBin(binPath) {
  const cuePath = binPath.replace(/\.bin$/i, '.cue');
  const binName = path.basename(binPath);
  fs.writeFileSync(cuePath,
    `FILE "${binName}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`);
  return cuePath;
}

function getBinsFromCue(cuePath) {
  const content = fs.readFileSync(cuePath, 'utf-8');
  const bins = [];
  const dir = path.dirname(cuePath);
  for (const line of content.split('\n')) {
    const match = line.match(/FILE\s+"([^"]+)"/i);
    if (match) {
      const binPath = path.join(dir, match[1]);
      if (fs.existsSync(binPath)) bins.push(binPath);
    }
  }
  return bins;
}

// ── Processamento de um arquivo ───────────────────────────────────────────

async function processOne(archive, results) {
  const chdName = buildChdName(archive.name);
  const chdDestPath = path.join(OUTPUT_DIR, chdName);

  // Verifica se já existe
  if (chdExists(chdName)) {
    log(`  SKIP (já existe): ${archive.name} → ${chdName}`);
    results.skipped.push({ file: archive.name, chd: chdName, reason: 'já existe' });
    return;
  }

  const startTime = Date.now();
  const tempDir = path.join(TEMP_BASE, `job_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);

  try {
    fs.mkdirSync(tempDir, { recursive: true });

    // 1. Extrair ou copiar
    if (archive.ext === '.bin') {
      // Copia o .bin para o temp dir
      const destBin = path.join(tempDir, archive.name);
      fs.copyFileSync(archive.path, destBin);
    } else {
      log(`  Extraindo: ${archive.name}`);
      const extractResult = await extractArchive(archive.path, tempDir);
      if (!extractResult.success) {
        throw new Error(`Falha na extração: ${extractResult.error.slice(0, 200)}`);
      }
    }

    // 2. Procurar .cue e .bin dentro do diretório temporário
    const allFiles = fs.readdirSync(tempDir);
    const cueFiles = allFiles.filter(f => f.toLowerCase().endsWith('.cue'));
    const binFiles = allFiles.filter(f => f.toLowerCase().endsWith('.bin'));
    const imgFiles = allFiles.filter(f => f.toLowerCase().endsWith('.img'));

    let cueToConvert = null;
    let chdPathInTemp = path.join(tempDir, chdName);

    if (cueFiles.length > 0) {
      // Usa o primeiro .cue que tem .bin correspondente
      for (const cue of cueFiles) {
        const cuePath = path.join(tempDir, cue);
        const bins = getBinsFromCue(cuePath);
        if (bins.length > 0) {
          cueToConvert = cuePath;
          break;
        }
      }
      // Se nenhum .cue tem .bin referenciado, usa o primeiro mesmo assim
      if (!cueToConvert && cueFiles.length > 0) {
        cueToConvert = path.join(tempDir, cueFiles[0]);
      }
    } else if (binFiles.length > 0) {
      // .bin sem .cue — gera .cue simples para o maior .bin
      const bins = binFiles
        .map(f => ({ name: f, path: path.join(tempDir, f), size: fs.statSync(path.join(tempDir, f)).size }))
        .sort((a, b) => b.size - a.size);
      const largestBin = bins[0];
      if (largestBin && largestBin.size > 1024 * 1024) {
        cueToConvert = generateCueForBin(largestBin.path);
      }
    } else if (imgFiles.length > 0) {
      // .img sem .cue — gera .cue
      const imgPath = path.join(tempDir, imgFiles[0]);
      const cuePath = imgPath.replace(/\.img$/i, '.cue');
      fs.writeFileSync(cuePath,
        `FILE "${imgFiles[0]}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`);
      cueToConvert = cuePath;
    }

    if (!cueToConvert) {
      throw new Error('Nenhum .cue/.bin/.img encontrado após extração');
    }

    // 3. Converter com chdman
    log(`  Convertendo: ${archive.name} → ${chdName}`);
    const convertResult = await convertCueToChd(cueToConvert, chdPathInTemp);

    if (!convertResult.success || !fs.existsSync(chdPathInTemp) || fs.statSync(chdPathInTemp).size < 1024 * 1024) {
      const errMsg = convertResult.error ? convertResult.error.slice(0, 300) : 'CHD muito pequeno ou inexistente';
      throw new Error(`chdman falhou: ${errMsg}`);
    }

    // 4. Mover .chd para F:\testes
    fs.copyFileSync(chdPathInTemp, chdDestPath);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    const sizeMB = (fs.statSync(chdDestPath).size / (1024 * 1024)).toFixed(0);
    log(`  OK: ${chdName} (${sizeMB}MB, ${elapsed}s)`);
    results.converted.push({
      file: archive.name,
      chd: chdName,
      sizeMB: parseInt(sizeMB),
      timeSec: parseFloat(elapsed),
    });

  } catch (err) {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    log(`  FALHA: ${archive.name} — ${err.message} (${elapsed}s)`);
    results.failed.push({
      file: archive.name,
      chd: chdName,
      error: err.message,
      timeSec: parseFloat(elapsed),
    });
  } finally {
    // 5. Limpeza do diretório temporário
    try {
      fs.rmSync(tempDir, { recursive: true, force: true });
    } catch {
      // Tenta novamente após pequena espera
      await sleep(1000);
      try { fs.rmSync(tempDir, { recursive: true, force: true }); } catch {}
    }
  }
}

// ── Pool de concorrência (max 2 simultâneas) ──────────────────────────────

async function runPool(archives, results) {
  const queue = [...archives];
  const running = [];

  while (queue.length > 0 || running.length > 0) {
    // Preenche slots até MAX_CONCURRENT
    while (running.length < MAX_CONCURRENT && queue.length > 0) {
      const archive = queue.shift();
      const promise = processOne(archive, results).then(() => {
        running.splice(running.indexOf(promise), 1);
      });
      running.push(promise);
    }

    if (running.length > 0) {
      await Promise.race(running);
    }
  }
}

// ── Main ──────────────────────────────────────────────────────────────────

(async () => {
  const totalStart = Date.now();
  log('=== Conversão CHD em Lote ===');
  log(`Downloads: ${DOWNLOAD_DIR}`);
  log(`Saída:     ${OUTPUT_DIR}`);
  log(`chdman:    ${CHDMAN}`);
  log(`7-Zip:     ${SEVEN_ZIP}`);
  log(`Máx conc:  ${MAX_CONCURRENT}`);

  // Garante que diretórios existem
  if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  fs.mkdirSync(TEMP_BASE, { recursive: true });

  // Lista arquivos existentes em F:\testes
  const existingChds = fs.existsSync(OUTPUT_DIR)
    ? fs.readdirSync(OUTPUT_DIR).filter(f => f.toLowerCase().endsWith('.chd'))
    : [];
  log(`CHDs já existentes em ${OUTPUT_DIR}: ${existingChds.length}`);
  existingChds.forEach(f => log(`  - ${f}`));

  // Lista arquivos a processar
  const archives = listArchives();
  log(`\nArquivos encontrados: ${archives.length}`);

  // Filtra os que já têm .chd correspondente
  const toProcess = archives.filter(a => {
    const chdName = buildChdName(a.name);
    if (chdExists(chdName)) {
      log(`  SKIP (já convertido): ${a.name} → ${chdName}`);
      return false;
    }
    return true;
  });

  log(`Arquivos a converter: ${toProcess.length}\n`);

  const results = {
    converted: [],
    failed: [],
    skipped: [],
  };

  await runPool(toProcess, results);

  const totalElapsed = ((Date.now() - totalStart) / 1000).toFixed(1);
  const totalMin = (totalElapsed / 60).toFixed(1);

  log('\n=== RELATÓRIO FINAL ===');
  log(`Tempo total: ${totalElapsed}s (${totalMin} min)`);
  log(`Convertidos: ${results.converted.length}`);
  log(`Falhas:      ${results.failed.length}`);
  log(`Pulados:      ${results.skipped.length}`);

  if (results.converted.length > 0) {
    log('\n--- Convertidos ---');
    for (const r of results.converted) {
      log(`  ✓ ${r.file} → ${r.chd} (${r.sizeMB}MB, ${r.timeSec}s)`);
    }
  }

  if (results.failed.length > 0) {
    log('\n--- Falhas ---');
    for (const r of results.failed) {
      log(`  ✗ ${r.file} → ${r.chd}: ${r.error}`);
    }
  }

  // Escreve relatório em arquivo
  const reportPath = path.join(OUTPUT_DIR, '_conversion_report.json');
  fs.writeFileSync(reportPath, JSON.stringify({
    startTime: new Date(totalStart).toISOString(),
    endTime: new Date().toISOString(),
    totalSeconds: parseFloat(totalElapsed),
    converted: results.converted,
    failed: results.failed,
    skipped: results.skipped,
  }, null, 2));
  log(`\nRelatório salvo: ${reportPath}`);

  // Limpa diretório temporário base
  try { fs.rmSync(TEMP_BASE, { recursive: true, force: true }); } catch {}

  process.exit(0);
})();
