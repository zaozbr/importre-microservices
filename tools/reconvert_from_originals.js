#!/usr/bin/env node
/**
 * Reconverte CHDs a partir dos .bin/.cue originais em D:\roms\duplicados.
 * Para cada jogo: encontra o .bin principal (com serial SLPS/SLES/SLUS/SCPS/SCES/SCUS/SLPM),
 * cria CUE com trilha 1 = dados e demais = audio, e roda chdman createcd.
 *
 * Uso: node tools/reconvert_from_originals.js [--dry-run] [--prefix "Nome"]
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PSX_DIR = 'D:\\roms\\library\\roms\\psx';
const DUP_DIR = 'D:\\roms\\duplicados';
const CHDMAN = 'F:\\importre\\chdman.exe';
const TMP_DIR = 'F:\\importre\\_tmp_reconvert';

const args = process.argv.slice(2);
const dryRun = args.includes('--dry-run');
const prefixFilter = args.includes('--prefix') ? args[args.indexOf('--prefix') + 1] : null;

// Jogos afetados (prefixo para buscar em duplicados)
const games = [
  { prefix: 'Eisei-Meijin-II', chdName: 'Eisei-Meijin-II-SLPM-86014.chd' },
  { prefix: 'Zen-Nihon-GT-Senshuken', chdName: null },
];

function findBinFiles(prefix) {
  const all = fs.readdirSync(DUP_DIR).filter(f => f.toLowerCase().startsWith(prefix.toLowerCase()));
  return all.filter(f => f.endsWith('.bin')).sort();
}

function findSerial(binPath) {
  const buf = fs.readFileSync(binPath);
  const str = buf.toString('latin1', 0, Math.min(buf.length, 200000));
  // Formato PS1: "SLPM_860.14;1" ou "SLPS_007.16" -> serial "SLPM-86014"
  const match = str.match(/(SLPM|SLPS|SLES|SLUS|SCPS|SCES|SCUS)[_-]?(\d{3})[._]?(\d{2})/);
  if (match) {
    return `${match[1]}-${match[2]}${match[3]}`;
  }
  return null;
}

function reconvertGame(prefix, chdName) {
  console.log(`\n=== ${prefix} ===`);
  const bins = findBinFiles(prefix);
  if (bins.length === 0) {
    console.log(`  SEM .bin originais - pular (rebaixar)`);
    return { prefix, status: 'NO_ORIGINALS' };
  }

  // Encontrar o .bin principal (sem _N) - deve ter o serial
  const mainBin = bins.find(f => !/_\d+\.bin$/.test(f));
  const trackBins = bins.filter(f => /_\d+\.bin$/.test(f)).sort((a, b) => {
    const na = parseInt(a.match(/_(\d+)\.bin$/)[1]);
    const nb = parseInt(b.match(/_(\d+)\.bin$/)[1]);
    return na - nb;
  });

  if (!mainBin) {
    console.log(`  SEM .bin principal - pular`);
    return { prefix, status: 'NO_MAIN_BIN' };
  }

  console.log(`  .bin principal: ${mainBin} (${(fs.statSync(path.join(DUP_DIR, mainBin)).size / 1048576).toFixed(1)}MB)`);
  console.log(`  Trilhas de audio: ${trackBins.length}`);

  // Descobrir serial
  const serial = findSerial(path.join(DUP_DIR, mainBin));
  console.log(`  Serial: ${serial || 'NAO ENCONTRADO'}`);

  if (dryRun) {
    console.log('  [DRY-RUN] Pulando conversao');
    return { prefix, status: 'DRY_RUN', serial, trackCount: trackBins.length };
  }

  // Preparar diretorio temporario
  const gameTmp = path.join(TMP_DIR, prefix.replace(/[^a-zA-Z0-9]/g, '_'));
  if (fs.existsSync(gameTmp)) fs.rmSync(gameTmp, { recursive: true, force: true });
  fs.mkdirSync(gameTmp, { recursive: true });

  // Copiar e renomear trilhas
  const binFiles = [];
  fs.copyFileSync(path.join(DUP_DIR, mainBin), path.join(gameTmp, 'track01.bin'));
  binFiles.push('track01.bin');

  for (let i = 0; i < trackBins.length; i++) {
    const trackNum = (i + 2).toString().padStart(2, '0');
    fs.copyFileSync(path.join(DUP_DIR, trackBins[i]), path.join(gameTmp, `track${trackNum}.bin`));
    binFiles.push(`track${trackNum}.bin`);
  }

  // Criar CUE
  let cue = '';
  for (let i = 0; i < binFiles.length; i++) {
    const trackNum = (i + 1).toString().padStart(2, '0');
    if (i === 0) {
      cue += `FILE "${binFiles[i]}" BINARY\r\n  TRACK ${trackNum} MODE2/2352\r\n    INDEX 01 00:00:00\r\n`;
    } else {
      cue += `FILE "${binFiles[i]}" BINARY\r\n  TRACK ${trackNum} AUDIO\r\n    INDEX 01 00:00:00\r\n`;
    }
  }
  const cuePath = path.join(gameTmp, 'game.cue');
  fs.writeFileSync(cuePath, cue, 'ascii');

  // Nome do CHD de saida
  let outChdName = chdName;
  if (!outChdName && serial) {
    outChdName = `${prefix}-${serial}.chd`;
  } else if (!outChdName) {
    outChdName = `${prefix}.chd`;
  }

  const outChdPath = path.join(PSX_DIR, outChdName);

  // Deletar CHD antigo se existir
  if (fs.existsSync(outChdPath)) {
    fs.unlinkSync(outChdPath);
  }

  // Converter
  console.log(`  Convertendo -> ${outChdName}...`);
  try {
    execSync(`"${CHDMAN}" createcd -i "${cuePath}" -o "${outChdPath}" -f`, {
      stdio: 'pipe',
      timeout: 600000,
    });
  } catch (e) {
    console.error(`  ERRO: ${e.message}`);
    fs.rmSync(gameTmp, { recursive: true, force: true });
    return { prefix, status: 'CONVERT_ERROR' };
  }

  if (!fs.existsSync(outChdPath)) {
    console.error(`  FALHA: CHD nao criado`);
    fs.rmSync(gameTmp, { recursive: true, force: true });
    return { prefix, status: 'CONVERT_FAILED' };
  }

  const sizeMB = (fs.statSync(outChdPath).size / 1048576).toFixed(1);
  console.log(`  CHD criado: ${outChdName} (${sizeMB}MB)`);

  // Limpar
  fs.rmSync(gameTmp, { recursive: true, force: true });

  return { prefix, status: 'OK', chdName: outChdName, sizeMB, serial, trackCount: trackBins.length + 1 };
}

// === Main ===
console.log('=== Reconversao de CHDs a partir de originais ===\n');
const results = [];

for (const game of games) {
  if (prefixFilter && !game.prefix.includes(prefixFilter)) continue;
  const result = reconvertGame(game.prefix, game.chdName);
  results.push(result);
}

console.log('\n=== Resultado ===');
for (const r of results) {
  console.log(`  ${r.prefix}: ${r.status}${r.chdName ? ` (${r.chdName}, ${r.sizeMB}MB)` : ''}`);
}
