/**
 * chd_worker.js — Processo dedicado para conversão CHD
 *
 * Monitora F:\downloads em busca de pastas isoladas com arquivos
 * .bin/.cue/.img/.7z/.zip/.rar e converte para .chd.
 *
 * Fluxo:
 * 1. Detecta pastas em F:\downloads com arquivos de midia
 * 2. Extrai arquivos compactados se houver
 * 3. Converte .cue+.bin / .bin orfao / .img para .chd (max 2 simultaneo)
 * 4. Move .chd para D:\roms\library\roms\psx
 * 5. Move arquivos de origem para D:\roms\duplicados
 * 6. Apaga pasta de conversao
 *
 * Roda em processo SEPARADO do download service para nao bloquear o event loop.
 */
const fs = require('fs');
const path = require('path');
const { spawn, execSync } = require('child_process');
const { PSX_DIR, DOWNLOAD_DIR, DUP_DIR, CHDMAN_PATH } = require('../shared/config');

const SEVEN_ZIP = process.env.SEVEN_ZIP_PATH || 'C:\\Program Files\\7-Zip\\7z.exe';
const POLL_INTERVAL = 5000;
const MAX_CONCURRENT = 2;

if (!fs.existsSync(DUP_DIR)) fs.mkdirSync(DUP_DIR, { recursive: true });
if (!fs.existsSync(PSX_DIR)) fs.mkdirSync(PSX_DIR, { recursive: true });

function log(msg) {
  console.log(`[${new Date().toISOString()}] [chd-worker] ${msg}`);
}

const activeConversions = new Set();

function convertCueToChd(cuePath, chdPath) {
  return new Promise((resolve) => {
    const proc = spawn(CHDMAN_PATH, ['createcd', '-i', cuePath, '-o', chdPath, '-f'], {
      cwd: path.dirname(cuePath),
      windowsHide: true,
    });
    let stderr = '';
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => resolve({ success: code === 0, error: stderr }));
    proc.on('error', (e) => resolve({ success: false, error: e.message }));
  });
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

function generateCueForBin(binPath) {
  const cuePath = binPath.replace(/\.bin$/i, '.cue');
  const binName = path.basename(binPath);
  fs.writeFileSync(cuePath, `FILE "${binName}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`);
  return cuePath;
}

function moveToDuplicados(filePath) {
  if (!fs.existsSync(filePath)) return;
  const name = path.basename(filePath);
  let dest = path.join(DUP_DIR, name);
  let counter = 1;
  while (fs.existsSync(dest)) {
    const ext = path.extname(name);
    const base = path.basename(name, ext);
    dest = path.join(DUP_DIR, `${base}_${counter}${ext}`);
    counter++;
  }
  try {
    fs.renameSync(filePath, dest);
  } catch {
    try { fs.copyFileSync(filePath, dest); fs.unlinkSync(filePath); } catch {}
  }
}

function extractArchive(archPath, destDir) {
  return new Promise((resolve) => {
    const proc = spawn(SEVEN_ZIP, ['x', '-y', `-o${destDir}`, archPath], { cwd: destDir, windowsHide: true });
    let stderr = '';
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => resolve({ success: code === 0, error: stderr }));
    proc.on('error', (e) => resolve({ success: false, error: e.message }));
  });
}

async function processDir(dir) {
  const name = path.basename(dir);
  if (activeConversions.has(dir)) return;
  activeConversions.add(dir);

  try {
    log(`Processando: ${name}`);

    // 1. Extrair arquivos compactados
    const archives = fs.readdirSync(dir).filter(f => /\.(7z|zip|rar)$/i.test(f));
    for (const arch of archives) {
      const archPath = path.join(dir, arch);
      log(`  Extraindo: ${arch}`);
      const result = await extractArchive(archPath, dir);
      if (result.success) {
        try { fs.unlinkSync(archPath); } catch {}
        log(`  Extraido: ${arch}`);
      } else {
        log(`  Erro ao extrair: ${arch} - ${result.error.substring(0, 100)}`);
      }
    }

    // 2. Converter .cue + .bin para .chd
    const chdFiles = [];
    const cueFiles = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.cue'));
    for (const cue of cueFiles) {
      const cuePath = path.join(dir, cue);
      const bins = getBinsFromCue(cuePath);
      if (!bins.length) continue;

      const stem = path.basename(cue, '.cue');
      const chdName = stem.replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') + '.chd';
      const chdPath = path.join(dir, chdName);

      if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
        chdFiles.push(chdPath);
        continue;
      }

      log(`  Convertendo: ${cue} -> ${chdName}`);
      const result = await convertCueToChd(cuePath, chdPath);
      if (result.success && fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
        chdFiles.push(chdPath);
        log(`  OK: ${chdName} (${Math.round(fs.statSync(chdPath).size / 1048576)}MB)`);
      } else {
        log(`  Falhou: ${cue} - ${result.error.substring(0, 100)}`);
      }
    }

    // 3. Converter .bin orfaos
    const binFiles = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.bin'));
    for (const bin of binFiles) {
      const binPath = path.join(dir, bin);
      const cuePath = binPath.replace(/\.bin$/i, '.cue');
      if (fs.existsSync(cuePath)) continue;
      if (fs.statSync(binPath).size < 1048576) continue;

      const tmpCue = generateCueForBin(binPath);
      const stem = path.basename(bin, '.bin');
      const chdName = stem.replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') + '.chd';
      const chdPath = path.join(dir, chdName);

      if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
        chdFiles.push(chdPath);
        try { fs.unlinkSync(tmpCue); } catch {}
        continue;
      }

      log(`  Convertendo .bin orfao: ${bin}`);
      const result = await convertCueToChd(tmpCue, chdPath);
      if (result.success && fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
        chdFiles.push(chdPath);
        log(`  OK: ${chdName}`);
      }
      try { fs.unlinkSync(tmpCue); } catch {}
    }

    // 4. Converter .img
    const imgFiles = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.img'));
    for (const img of imgFiles) {
      const imgPath = path.join(dir, img);
      if (fs.statSync(imgPath).size < 1048576) continue;
      const cuePath = imgPath.replace(/\.img$/i, '.cue');
      fs.writeFileSync(cuePath, `FILE "${img}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`);
      const stem = path.basename(img, '.img');
      const chdName = stem.replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') + '.chd';
      const chdPath = path.join(dir, chdName);
      log(`  Convertendo .img: ${img}`);
      const result = await convertCueToChd(cuePath, chdPath);
      if (result.success && fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
        chdFiles.push(chdPath);
      }
      try { fs.unlinkSync(cuePath); } catch {}
    }

    // 5. Incluir .chd ja existentes
    const existingChds = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.chd'));
    for (const chd of existingChds) {
      const chdPath = path.join(dir, chd);
      if (fs.statSync(chdPath).size > 1048576 && !chdFiles.includes(chdPath)) {
        chdFiles.push(chdPath);
      }
    }

    // 6. Mover .chd para PSX_DIR
    for (const chdFile of chdFiles) {
      const chdDest = path.join(PSX_DIR, path.basename(chdFile));
      try {
        if (fs.existsSync(chdDest)) moveToDuplicados(chdDest);
        fs.renameSync(chdFile, chdDest);
        log(`  CHD movido: ${path.basename(chdFile)}`);
      } catch {
        try { fs.copyFileSync(chdFile, chdDest); fs.unlinkSync(chdFile); } catch {}
      }
    }

    // 7. Mover origens para duplicados
    const originExts = ['.bin', '.cue', '.img', '.ccd', '.sub', '.mdf', '.mds', '.ecm', '.iso', '.ape'];
    for (const f of fs.readdirSync(dir)) {
      const fp = path.join(dir, f);
      if (fs.statSync(fp).isFile()) {
        const ext = path.extname(f).toLowerCase();
        if (originExts.includes(ext) || ext === '.zip' || ext === '.7z' || ext === '.rar') {
          moveToDuplicados(fp);
        }
      }
    }

    // 8. Apagar pasta de conversao
    try { fs.rmSync(dir, { recursive: true, force: true }); } catch {}
    log(`  Concluido: ${name} (${chdFiles.length} CHDs)`);

  } catch (e) {
    log(`  ERRO em ${name}: ${e.message}`);
  } finally {
    activeConversions.delete(dir);
  }
}

async function loop() {
  log(`CHD Worker iniciado. Monitorando: ${DOWNLOAD_DIR}`);
  log(`CHDMAN: ${CHDMAN_PATH} | PSX_DIR: ${PSX_DIR} | DUP_DIR: ${DUP_DIR}`);

  while (true) {
    try {
      if (!fs.existsSync(DOWNLOAD_DIR)) {
        fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });
      }

      // Detectar pastas isoladas (F:\downloads\<serial>\)
      const dirs = fs.readdirSync(DOWNLOAD_DIR, { withFileTypes: true })
        .filter(d => d.isDirectory())
        .map(d => path.join(DOWNLOAD_DIR, d.name))
        .filter(d => !activeConversions.has(d));

      // Processar ate MAX_CONCURRENT simultaneamente
      const available = MAX_CONCURRENT - activeConversions.size;
      const toProcess = dirs.slice(0, available);

      // Tambem processar .chd soltos (download direto de CHD)
      const looseChds = fs.readdirSync(DOWNLOAD_DIR, { withFileTypes: true })
        .filter(f => f.isFile() && f.name.toLowerCase().endsWith('.chd'))
        .map(f => path.join(DOWNLOAD_DIR, f.name));

      for (const chdPath of looseChds) {
        try {
          const chdDest = path.join(PSX_DIR, path.basename(chdPath));
          if (fs.existsSync(chdDest)) moveToDuplicados(chdDest);
          fs.renameSync(chdPath, chdDest);
          log(`CHD direto movido: ${path.basename(chdPath)}`);
        } catch {
          try { fs.copyFileSync(chdPath, path.join(PSX_DIR, path.basename(chdPath))); fs.unlinkSync(chdPath); } catch {}
        }
      }

      // Processar pastas em paralelo (ate MAX_CONCURRENT)
      if (toProcess.length > 0) {
        await Promise.all(toProcess.map(processDir));
      }
    } catch (e) {
      log(`Loop erro: ${e.message}`);
    }
    await new Promise(r => setTimeout(r, POLL_INTERVAL));
  }
}

loop();
