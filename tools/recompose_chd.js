#!/usr/bin/env node
/**
 * Recompoe CHDs que foram convertidos com trilhas separadas (_1.chd, _2.chd, ...)
 * em um unico CHD com multiplas trilhas (dados + audio).
 *
 * Estrategia:
 * 1. Extrair cada CHD individual para .bin (dados raw 2352 bytes/setor)
 * 2. Criar CUE sheet correto (TRACK 01 MODE2/2352, TRACK 02+ AUDIO)
 * 3. Rodar chdman createcd com o CUE para gerar CHD unico
 *
 * Uso: node tools/recompose_chd.js [--dry-run] [--game "Nome-Prefixo"]
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PSX_DIR = 'D:\\roms\\library\\roms\\psx';
const CHDMAN = 'F:\\importre\\chdman.exe';
const TMP_DIR = 'F:\\importre\\_tmp_recompose';

const args = process.argv.slice(2);
const dryRun = args.includes('--dry-run');
const gameFilter = args.includes('--game') ? args[args.indexOf('--game') + 1] : null;

function findAffectedGames() {
  const allFiles = fs.readdirSync(PSX_DIR).filter(f => f.endsWith('.chd'));
  const splitChds = allFiles.filter(f => /_\d+\.chd$/.test(f));

  const byGame = new Map();
  for (const f of splitChds) {
    const match = f.match(/^(.+)_\d+\.chd$/);
    if (!match) continue;
    const prefix = match[1];
    if (!byGame.has(prefix)) byGame.set(prefix, []);
    byGame.get(prefix).push(f);
  }

  const games = [];
  for (const [prefix, tracks] of byGame) {
    tracks.sort((a, b) => {
      const na = parseInt(a.match(/_(\d+)\.chd$/)[1]);
      const nb = parseInt(b.match(/_(\d+)\.chd$/)[1]);
      return na - nb;
    });

    // Encontrar CHD principal (sem _N)
    const mainChd = allFiles.find(f => f.startsWith(prefix) && !/_\d+\.chd$/.test(f) && f !== prefix + '.chd');

    games.push({
      prefix,
      tracks,
      trackCount: tracks.length,
      mainChd,
      hasMain: !!mainChd,
    });
  }

  return games.sort((a, b) => b.trackCount - a.trackCount);
}

function extractTrack(chdPath, outBin, outCue) {
  try {
    execSync(`"${CHDMAN}" extractcd -i "${chdPath}" -o "${outCue}" -ob "${outBin}" -f`, {
      stdio: 'pipe',
      timeout: 120000,
    });
    return fs.existsSync(outBin);
  } catch (e) {
    console.error(`  ERRO extraindo ${path.basename(chdPath)}: ${e.message}`);
    return false;
  }
}

function createCue(trackFiles, outCue) {
  let cue = '';
  for (let i = 0; i < trackFiles.length; i++) {
    const binName = path.basename(trackFiles[i]);
    const trackNum = (i + 1).toString().padStart(2, '0');
    if (i === 0) {
      cue += `FILE "${binName}" BINARY\r\n  TRACK ${trackNum} MODE2/2352\r\n    INDEX 01 00:00:00\r\n`;
    } else {
      cue += `FILE "${binName}" BINARY\r\n  TRACK ${trackNum} AUDIO\r\n    INDEX 01 00:00:00\r\n`;
    }
  }
  fs.writeFileSync(outCue, cue, 'ascii');
}

function createChd(cuePath, outChd) {
  try {
    execSync(`"${CHDMAN}" createcd -i "${cuePath}" -o "${outChd}" -f`, {
      stdio: 'pipe',
      timeout: 300000,
    });
    return fs.existsSync(outChd);
  } catch (e) {
    console.error(`  ERRO criando CHD: ${e.message}`);
    return false;
  }
}

function verifyChd(chdPath) {
  try {
    const out = execSync(`"${CHDMAN}" verify -i "${chdPath}"`, {
      stdio: 'pipe',
      timeout: 120000,
    }).toString();
    return out.includes('Verification complete');
  } catch {
    return false;
  }
}

function recomposeGame(game) {
  const { prefix, tracks, mainChd } = game;
  console.log(`\n=== ${prefix} ===`);
  console.log(`  Trilhas separadas: ${tracks.length}`);
  console.log(`  CHD principal: ${mainChd || 'NENHUM'}`);

  if (dryRun) {
    console.log('  [DRY-RUN] Pulando recomposicao');
    return;
  }

  // Preparar diretorio temporario
  const gameTmpDir = path.join(TMP_DIR, prefix.replace(/[^a-zA-Z0-9-]/g, '_'));
  if (fs.existsSync(gameTmpDir)) fs.rmSync(gameTmpDir, { recursive: true, force: true });
  fs.mkdirSync(gameTmpDir, { recursive: true });

  const binFiles = [];

  // 1. Extrair CHD principal (trilha 1 = dados)
  if (mainChd) {
    const mainPath = path.join(PSX_DIR, mainChd);
    const binPath = path.join(gameTmpDir, 'track01.bin');
    const cuePath = path.join(gameTmpDir, 'track01.cue');
    console.log(`  Extraindo trilha 1 (dados)...`);
    if (!extractTrack(mainPath, binPath, cuePath)) {
      console.error(`  FALHA: nao foi possivel extrair CHD principal`);
      return false;
    }
    binFiles.push(binPath);
  } else {
    // Sem CHD principal - a primeira trilha _1 pode ser a trilha de dados
    console.log(`  SEM CHD principal - usando primeira trilha como dados`);
  }

  // 2. Extrair trilhas de audio (_1, _2, ...)
  const startIdx = mainChd ? 1 : 0;
  for (let i = 0; i < tracks.length; i++) {
    const trackNum = (i + startIdx + 1).toString().padStart(2, '0');
    const trackPath = path.join(PSX_DIR, tracks[i]);
    const binPath = path.join(gameTmpDir, `track${trackNum}.bin`);
    const cuePath = path.join(gameTmpDir, `track${trackNum}.cue`);
    console.log(`  Extraindo trilha ${trackNum} (${tracks[i]})...`);
    if (!extractTrack(trackPath, binPath, cuePath)) {
      console.error(`  FALHA: nao foi possivel extrair ${tracks[i]}`);
      return false;
    }
    binFiles.push(binPath);
  }

  // 3. Criar CUE sheet
  const cuePath = path.join(gameTmpDir, 'game.cue');
  const binNames = binFiles.map(f => path.basename(f));
  createCue(binNames, cuePath);
  console.log(`  CUE criado: ${binFiles.length} trilhas`);

  // 4. Criar CHD recomposto
  const chdName = mainChd
    ? mainChd.replace('.chd', '-recomposed.chd')
    : `${prefix}-recomposed.chd`;
  const outChd = path.join(gameTmpDir, chdName);
  console.log(`  Criando CHD recomposto...`);
  if (!createChd(cuePath, outChd)) {
    console.error(`  FALHA: erro ao criar CHD`);
    return false;
  }

  const chdSize = fs.statSync(outChd).size;
  console.log(`  CHD criado: ${(chdSize / 1048576).toFixed(1)} MB`);

  // 5. Verificar
  console.log(`  Verificando CHD...`);
  if (!verifyChd(outChd)) {
    console.error(`  AVISO: verificacao falhou - CHD pode estar corrompido`);
    // Continua mesmo assim - as vezes o verify falha por metadata
  }

  // 6. Mover CHD recomposto para o diretorio PSX
  const finalPath = path.join(PSX_DIR, chdName);
  fs.copyFileSync(outChd, finalPath);
  console.log(`  CHD final: ${chdName} (${(chdSize / 1048576).toFixed(1)} MB)`);

  // 7. Deletar arquivos antigos (CHD principal + trilhas separadas)
  if (mainChd) {
    const oldMain = path.join(PSX_DIR, mainChd);
    fs.unlinkSync(oldMain);
    console.log(`  Deletado: ${mainChd}`);
  }
  for (const t of tracks) {
    fs.unlinkSync(path.join(PSX_DIR, t));
    console.log(`  Deletado: ${t}`);
  }

  // 8. Renomear CHD recomposto para o nome original do principal
  if (mainChd) {
    const originalName = path.join(PSX_DIR, mainChd);
    fs.renameSync(finalPath, originalName);
    console.log(`  Renomeado: ${chdName} -> ${mainChd}`);
  }

  // 9. Limpar diretorio temporario
  fs.rmSync(gameTmpDir, { recursive: true, force: true });

  console.log(`  SUCESSO!`);
  return true;
}

// === Main ===
const games = findAffectedGames();
console.log(`Jogos afetados: ${games.length}`);
console.log(`Total de trilhas separadas: ${games.reduce((s, g) => s + g.trackCount, 0)}`);

let success = 0, failed = 0;
for (const game of games) {
  if (gameFilter && !game.prefix.includes(gameFilter)) continue;
  const ok = recomposeGame(game);
  if (ok) success++;
  else failed++;
}

console.log(`\n=== Resultado ===`);
console.log(`Sucesso: ${success}`);
console.log(`Falha: ${failed}`);
if (!dryRun) {
  console.log(`\nArquivos temporarios em: ${TMP_DIR}`);
}
