/**
 * convert_all_to_chd.js
 *
 * Converte TODOS os arquivos nao-CHD em D:\roms\library\roms\psx e F:\chd_temp
 * para .chd usando chdman.exe. Apos converter, move os arquivos de origem
 * (.bin, .cue, .img, .ccd, .sub, .mdf, .mds, .ecm) para D:\roms\duplicados.
 *
 * Fluxo:
 * 1. Para cada .cue encontrado, converter .cue+.bin -> .chd
 * 2. Para .bin orfao (sem .cue), gerar .cue temporario e converter
 * 3. Para .img, renomear para .bin se tiver .cue correspondente
 * 4. Para .mdf/.mds, converter (gerar .cue)
 * 5. Para .ecm, descomprimir com unecm ou cmd
 * 6. Mover origens para D:\roms\duplicados
 * 7. Apagar .aria2 (downloads incompletos)
 */
const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

const PSX_DIR = 'D:\\roms\\library\\roms\\psx';
const CHD_TEMP = 'F:\\chd_temp';
const DUPLICADOS = 'D:\\roms\\duplicados';
const CHDMAN = 'D:\\roms\\library\\roms\\psx\\chdman.exe';
const SEVEN_ZIP = 'C:\\Program Files\\7-Zip\\7z.exe';

if (!fs.existsSync(DUPLICADOS)) fs.mkdirSync(DUPLICADOS, { recursive: true });

function log(msg) {
  console.log(`[${new Date().toISOString()}] ${msg}`);
}

/**
 * Converte .cue + .bin para .chd usando chdman.
 */
function convertCueToChd(cuePath, chdPath) {
  return new Promise((resolve) => {
    const proc = spawn(CHDMAN, ['createcd', '-i', cuePath, '-o', chdPath, '-f'], {
      cwd: path.dirname(cuePath),
      windowsHide: true,
    });
    let stderr = '';
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => {
      resolve({ success: code === 0, error: stderr });
    });
    proc.on('error', (e) => {
      resolve({ success: false, error: e.message });
    });
  });
}

/**
 * Move arquivo para D:\roms\duplicados
 */
function moveToDuplicados(filePath) {
  const name = path.basename(filePath);
  const dest = path.join(DUPLICADOS, name);
  // Se ja existe, adiciona sufixo
  let finalDest = dest;
  let counter = 1;
  while (fs.existsSync(finalDest)) {
    const ext = path.extname(name);
    const base = path.basename(name, ext);
    finalDest = path.join(DUPLICADOS, `${base}_${counter}${ext}`);
    counter++;
  }
  try {
    fs.renameSync(filePath, finalDest);
    log(`  Movido para duplicados: ${name}`);
  } catch (e) {
    // Se falhar (ex: cross-drive), copiar e deletar
    try {
      fs.copyFileSync(filePath, finalDest);
      fs.unlinkSync(filePath);
      log(`  Copiado+deletado para duplicados: ${name}`);
    } catch (e2) {
      log(`  ERRO ao mover ${name}: ${e2.message}`);
    }
  }
}

/**
 * Gera um .cue temporario para um .bin orfao
 */
function generateCue(binPath) {
  const cuePath = binPath.replace(/\.bin$/i, '.cue');
  const binName = path.basename(binPath);
  const cueContent = `FILE "${binName}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`;
  fs.writeFileSync(cuePath, cueContent);
  return cuePath;
}

/**
 * Le um .cue e retorna lista de .bin referenciados
 */
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

/**
 * Processa um diretorio: encontra .cue, converte, move origens
 */
function cleanupJunkFiles(dir) {
  // 1. Apagar .aria2 (downloads incompletos)
  const aria2Files = fs.readdirSync(dir).filter(f => f.endsWith('.aria2') || f.endsWith('.aria2__temp'));
  for (const f of aria2Files) {
    const fp = path.join(dir, f);
    try { fs.unlinkSync(fp); log(`  Apagado .aria2: ${f}`); } catch {}
  }

  // 2. Apagar .txt e .html (lixo)
  const junkFiles = fs.readdirSync(dir).filter(f => /\.(txt|html|exe)$/i.test(f) && f !== 'chdman.exe');
  for (const f of junkFiles) {
    const fp = path.join(dir, f);
    try { fs.unlinkSync(fp); log(`  Apagado lixo: ${f}`); } catch {}
  }

  // 3. Apagar arquivos nao-PSX (.gbc, .nes, .md)
  const nonPsxFiles = fs.readdirSync(dir).filter(f => /\.(gbc|nes|md)$/i.test(f));
  for (const f of nonPsxFiles) {
    const fp = path.join(dir, f);
    moveToDuplicados(fp);
  }
}

function extractArchives(dir) {
  // 4. Extrair arquivos compactados (.7z, .zip, .rar)
  const archives = fs.readdirSync(dir).filter(f => /\.(7z|zip|rar)$/i.test(f));
  for (const arch of archives) {
    const archPath = path.join(dir, arch);
    log(`  Extraindo: ${arch}`);
    try {
      execSync(`"${SEVEN_ZIP}" x -y -o"${dir}" "${archPath}"`, { windowsHide: true, timeout: 120000 });
      fs.unlinkSync(archPath);
      log(`  Extraido e apagado: ${arch}`);
    } catch (e) {
      log(`  ERRO ao extrair ${arch}: ${e.message}`);
    }
  }
}

function cleanChdName(stem) {
  return stem.replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') + '.chd';
}

async function convertCueFiles(dir) {
  // 5. Converter .cue + .bin para .chd
  const cueFiles = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.cue'));
  for (const cue of cueFiles) {
    const cuePath = path.join(dir, cue);
    const bins = getBinsFromCue(cuePath);
    if (!bins.length) {
      log(`  .cue sem bins: ${cue} - pulando`);
      moveToDuplicados(cuePath);
      continue;
    }

    // Nome do .chd baseado no .cue
    const stem = path.basename(cue, '.cue');
    const chdName = cleanChdName(stem);
    const chdPath = path.join(dir, chdName);

    // Se .chd ja existe e e valido (>1MB), pular
    if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
      log(`  .chd ja existe: ${chdName} - movendo origens`);
      for (const b of bins) moveToDuplicados(b);
      moveToDuplicados(cuePath);
      continue;
    }

    log(`  Convertendo: ${cue} -> ${chdName}`);
    const result = await convertCueToChd(cuePath, chdPath);
    if (result.success) {
      log(`  OK: ${chdName} (${Math.round(fs.statSync(chdPath).size / 1048576)}MB)`);
      // Mover origens para duplicados
      for (const b of bins) moveToDuplicados(b);
      moveToDuplicados(cuePath);
    } else {
      log(`  FALHOU: ${cue} - ${result.error.substring(0, 200)}`);
      // Mover mesmo assim (nao conversivel)
      for (const b of bins) moveToDuplicados(b);
      moveToDuplicados(cuePath);
      // Apagar .chd incompleto
      if (fs.existsSync(chdPath)) {
        try { fs.unlinkSync(chdPath); } catch {}
      }
    }
  }
}

async function convertOrphanBins(dir) {
  // 6. Converter .bin orfaos (sem .cue)
  const binFiles = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.bin'));
  for (const bin of binFiles) {
    const binPath = path.join(dir, bin);
    const cuePath = binPath.replace(/\.bin$/i, '.cue');
    if (fs.existsSync(cuePath)) continue; // tem cue, ja processado

    if (fs.statSync(binPath).size < 1048576) {
      log(`  .bin orfao muito pequeno: ${bin} - movendo`);
      moveToDuplicados(binPath);
      continue;
    }

    log(`  .bin orfao: ${bin} - gerando .cue`);
    const tmpCue = generateCue(binPath);
    const stem = path.basename(bin, '.bin');
    const chdName = cleanChdName(stem);
    const chdPath = path.join(dir, chdName);

    if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
      log(`  .chd ja existe: ${chdName}`);
      moveToDuplicados(binPath);
      try { fs.unlinkSync(tmpCue); } catch {}
      continue;
    }

    const result = await convertCueToChd(tmpCue, chdPath);
    if (result.success) {
      log(`  OK: ${chdName} (${Math.round(fs.statSync(chdPath).size / 1048576)}MB)`);
      moveToDuplicados(binPath);
    } else {
      log(`  FALHOU .bin orfao: ${bin} - ${result.error.substring(0, 200)}`);
      moveToDuplicados(binPath);
      if (fs.existsSync(chdPath)) { try { fs.unlinkSync(chdPath); } catch {} }
    }
    try { fs.unlinkSync(tmpCue); } catch {}
  }
}

async function convertImgFiles(dir) {
  // 7. Converter .img para .chd (gerar .cue)
  const imgFiles = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.img'));
  for (const img of imgFiles) {
    const imgPath = path.join(dir, img);
    if (fs.statSync(imgPath).size < 1048576) {
      moveToDuplicados(imgPath);
      continue;
    }
    log(`  .img: ${img} - gerando .cue`);
    const cuePath = imgPath.replace(/\.img$/i, '.cue');
    const imgName = path.basename(imgPath);
    const cueContent = `FILE "${imgName}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`;
    fs.writeFileSync(cuePath, cueContent);

    const stem = path.basename(img, '.img');
    const chdName = cleanChdName(stem);
    const chdPath = path.join(dir, chdName);

    const result = await convertCueToChd(cuePath, chdPath);
    if (result.success) {
      log(`  OK: ${chdName}`);
      moveToDuplicados(imgPath);
    } else {
      log(`  FALHOU .img: ${img}`);
      moveToDuplicados(imgPath);
      if (fs.existsSync(chdPath)) { try { fs.unlinkSync(chdPath); } catch {} }
    }
    try { fs.unlinkSync(cuePath); } catch {}
  }
}

function moveUnsupportedFormats(dir) {
  // 8. Mover .mdf, .mds, .ccd, .sub, .ecm para duplicados (formatos nao suportados pelo chdman)
  const otherExts = ['.mdf', '.mds', '.ccd', '.sub', '.ecm'];
  for (const ext of otherExts) {
    const files = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith(ext));
    for (const f of files) {
      moveToDuplicados(path.join(dir, f));
    }
  }
}

async function processDirectory(dir) {
  if (!fs.existsSync(dir)) { log(`Diretorio nao existe: ${dir}`); return; }
  log(`\n=== Processando: ${dir} ===`);

  cleanupJunkFiles(dir);
  extractArchives(dir);
  await convertCueFiles(dir);
  await convertOrphanBins(dir);
  await convertImgFiles(dir);
  moveUnsupportedFormats(dir);

  // 9. Processar subpastas
  const subdirs = fs.readdirSync(dir, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name);
  for (const sub of subdirs) {
    if (sub === 'chdman.exe' || sub.startsWith('.')) continue;
    await processDirectory(path.join(dir, sub));
  }
}

(async () => {
  log('=== INICIANDO CONVERSAO COMPLETA ===');

  // Processar F:\chd_temp primeiro
  await processDirectory(CHD_TEMP);

  // Processar D:\roms\library\roms\psx
  await processDirectory(PSX_DIR);

  log('\n=== CONVERSAO COMPLETA ===');

  // Relatorio final
  const remaining = fs.readdirSync(PSX_DIR).filter(f => {
    const ext = path.extname(f).toLowerCase();
    return ext !== '.chd' && f !== 'chdman.exe' && !f.endsWith('.aria2');
  });
  log(`Arquivos nao-CHD restantes em PSX_DIR: ${remaining.length}`);
  if (remaining.length > 0) {
    log('Restantes: ' + remaining.slice(0, 20).join(', '));
  }
})();
