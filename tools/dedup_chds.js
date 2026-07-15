/**
 * Dedup CHDs: para cada jogo com duplicados (N), testa o CHD principal primeiro.
 * Se principal OK (multi-trilha + tamanho razoavel + SHA1 unico), move duplicados para D:\roms\duplicados.
 * Se principal ruim, testa duplicados um por um no DuckStation.
 * O primeiro que funcionar e renomeado para o nome sem (N).
 *
 * Uso: node tools/dedup_chds.js [--dry-run] [--duck] [--limit N]
 *   --dry-run: so analisa, nao move/renomeia
 *   --duck: testa todos no DuckStation (lento)
 *   --limit N: processa no maximo N grupos
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PSX_DIR = 'D:\\roms\\library\\roms\\psx';
const DUP_DIR = 'D:\\roms\\duplicados';
const CHDMAN = 'F:\\importre\\chdman.exe';
const DUCK = 'C:\\Users\\Usuario\\AppData\\Local\\Programs\\DuckStation\\duckstation-qt-x64-ReleaseLTCG.exe';
const DUCK_LOG = 'C:\\Users\\Usuario\\Documents\\DuckStation\\duckstation.log';
const MEMCARD_DIR = 'C:\\Users\\Usuario\\Documents\\DuckStation\\memcards';
const QUEUE_PATH = 'D:\\roms\\library\\roms\\_importre_state\\queue.json';

const args = process.argv.slice(2);
const dryRun = args.includes('--dry-run');
const duckMode = args.includes('--duck');
const limitIdx = args.indexOf('--limit');
const limit = limitIdx >= 0 ? parseInt(args[limitIdx + 1]) : null;

function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function getChdInfo(chdPath) {
  try {
    const out = execSync(`"${CHDMAN}" info -i "${chdPath}"`, {
      stdio: 'pipe',
      timeout: 10000,
    }).toString();
    const trackMatches = [...out.matchAll(/TRACK:(\d+)\s+TYPE:(\w+)/g)];
    const tracks = trackMatches.map(m => ({ num: parseInt(m[1]), type: m[2] }));
    const sha1Match = out.match(/SHA1:\s+([0-9a-f]+)/i);
    const sha1 = sha1Match ? sha1Match[1] : null;
    const sizeMatch = out.match(/CHD size:\s+([\d,]+)\s+bytes/i);
    const chdSize = sizeMatch ? parseInt(sizeMatch[1].replace(/,/g, '')) : 0;
    const audioCount = tracks.filter(t => t.type === 'AUDIO').length;
    const dataCount = tracks.filter(t => t.type === 'MODE2_RAW' || t.type === 'MODE1_RAW' || t.type === 'MODE1' || t.type === 'MODE2').length;
    return {
      tracks,
      trackCount: tracks.length,
      audioCount,
      dataCount,
      sha1,
      chdSize,
      hasMultipleTracks: tracks.length > 1,
      hasAudio: audioCount > 0,
      hasData: dataCount > 0,
    };
  } catch (e) {
    return { tracks: [], trackCount: 0, audioCount: 0, dataCount: 0, sha1: null, chdSize: 0, hasMultipleTracks: false, hasAudio: false, hasData: false, error: e.message };
  }
}

function quickCheck(chdPath) {
  const info = getChdInfo(chdPath);
  const sizeMB = info.chdSize / 1048576;
  // CHD valido se: tem pelo menos 1 trilha de dados, tamanho > 3MB, e tem multiplas trilhas OU audio
  const valid = info.hasData && sizeMB > 3 && (info.hasMultipleTracks || info.hasAudio || sizeMB > 50);
  return { ...info, sizeMB, valid };
}

function testDuckStation(chdPath) {
  // Limpar log
  for (let i = 0; i < 5; i++) {
    try {
      if (fs.existsSync(DUCK_LOG)) fs.unlinkSync(DUCK_LOG);
      break;
    } catch (e) { sleep(2000); }
  }

  const memcardsBefore = new Set(fs.readdirSync(MEMCARD_DIR).filter(f => f.endsWith('.mcd')));

  try {
    execSync(`"${DUCK}" -batch -fastboot -earlyconsole -- "${chdPath}"`, {
      stdio: 'pipe',
      timeout: 35000,
    });
  } catch (e) { /* timeout esperado */ }

  sleep(3000);

  const memcardsAfter = new Set(fs.readdirSync(MEMCARD_DIR).filter(f => f.endsWith('.mcd')));
  const newMemcards = [...memcardsAfter].filter(m => !memcardsBefore.has(m));
  const log = fs.existsSync(DUCK_LOG) ? fs.readFileSync(DUCK_LOG, 'utf8') : '';
  const hasBoot = log.includes('System booted');
  const hasMemcardLine = log.includes('Memory Card 1:');
  const memcardCreated = newMemcards.length > 0 || hasMemcardLine;
  return hasBoot && memcardCreated;
}

function extractSerial(chdName) {
  const match = chdName.match(/(SLPS|SLES|SLUS|SCPS|SCES|SCUS|SLPM|SIPS|SCED|SLED)-(\d{5})/);
  return match ? `${match[1]}-${match[2]}` : null;
}

function moveToDup(chdName) {
  if (dryRun) { console.log(`  [DRY-RUN] Moveria: ${chdName}`); return; }
  const src = path.join(PSX_DIR, chdName);
  const dst = path.join(DUP_DIR, chdName);
  if (fs.existsSync(src)) fs.renameSync(src, dst);
}

function renameChd(oldName, newName) {
  if (dryRun) { console.log(`  [DRY-RUN] Renomearia: ${oldName} -> ${newName}`); return; }
  const src = path.join(PSX_DIR, oldName);
  const dst = path.join(PSX_DIR, newName);
  if (fs.existsSync(src)) fs.renameSync(src, dst);
}

function addToQueue(serial, title) {
  if (dryRun) { console.log(`  [DRY-RUN] Adicionaria na fila: ${serial}`); return; }
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
  } else {
    queue.queue.push({
      serial, title, status: 'pending', priority: 1,
      added: new Date().toISOString(), retry_count: 0,
      site_history: {}, sources: [],
    });
  }
  fs.writeFileSync(QUEUE_PATH, JSON.stringify(queue, null, 2));
}

// === Main ===
console.log('=== Dedup CHDs ===\n');

// Listar todos os CHDs
const allChds = fs.readdirSync(PSX_DIR).filter(f => f.endsWith('.chd'));

// Agrupar: base = nome sem (N)
const groups = new Map();
for (const f of allChds) {
  const base = f.replace(/\.chd$/, '').replace(/\s*\(\d+\)$/, '');
  if (!groups.has(base)) groups.set(base, { main: null, dupes: [] });
  if (/\(\d+\)\.chd$/.test(f)) {
    groups.get(base).dupes.push(f);
  } else {
    groups.get(base).main = f;
  }
}

// Filtrar so grupos com duplicados
const dupeGroups = [...groups.entries()].filter(([_, g]) => g.dupes.length > 0);
console.log(`Total de grupos com duplicados: ${dupeGroups.length}`);

let processed = 0;
let keptMain = 0;
let keptDupe = 0;
let allFailed = 0;
let duckTests = 0;

for (const [base, group] of dupeGroups) {
  if (limit && processed >= limit) break;
  processed++;

  const { main, dupes } = group;
  const allFiles = [main, ...dupes].filter(Boolean);

  console.log(`\n[${processed}/${dupeGroups.length}] ${base}`);
  console.log(`  Principal: ${main || 'NENHUM'} | Duplicados: ${dupes.length}`);

  // Filtro rapido com chdman info
  const checks = allFiles.map(f => {
    const info = quickCheck(path.join(PSX_DIR, f));
    return { file: f, ...info };
  });

  // Estrategia 1: se ha principal e ele passa no quickCheck, mover duplicados
  if (main) {
    const mainCheck = checks.find(c => c.file === main);
    if (mainCheck && mainCheck.valid) {
      console.log(`  Principal OK (quickCheck): ${mainCheck.trackCount} trilhas, ${mainCheck.sizeMB.toFixed(1)}MB`);
      // Verificar se algum duplicado tem SHA1 diferente (pode ser versao melhor)
      const mainSha1 = mainCheck.sha1;
      for (const c of checks.filter(x => x.file !== main)) {
        if (c.sha1 === mainSha1) {
          // Mesmo SHA1 = duplicado exato, mover
          moveToDup(c.file);
          console.log(`  -> Movido (SHA1 igual): ${c.file}`);
        } else if (c.valid && c.sizeMB > mainCheck.sizeMB * 1.2) {
          // Duplicado maior e valido - pode ser versao melhor, manter ambos por enquanto
          console.log(`  -> Mantido (SHA1 diferente, maior): ${c.file} (${c.sizeMB.toFixed(1)}MB)`);
        } else {
          // Duplicado menor ou invalido, mover
          moveToDup(c.file);
          console.log(`  -> Movido: ${c.file} (${c.sizeMB.toFixed(1)}MB, ${c.trackCount} trilhas)`);
        }
      }
      keptMain++;
      continue;
    } else if (mainCheck && !mainCheck.valid) {
      console.log(`  Principal RUIM (quickCheck): ${mainCheck.trackCount} trilhas, ${mainCheck.sizeMB.toFixed(1)}MB`);
    }
  }

  // Estrategia 2: principal ruim ou inexistente - testar duplicados com quickCheck
  const validDupes = checks.filter(c => c.file !== main && c.valid);
  const invalidDupes = checks.filter(c => c.file !== main && !c.valid);

  if (validDupes.length > 0) {
    // Ordenar por tamanho (maior primeiro = provavelmente mais completo)
    validDupes.sort((a, b) => b.sizeMB - a.sizeMB);
    const best = validDupes[0];
    console.log(`  Melhor duplicado (quickCheck): ${best.file} | ${best.trackCount} trilhas, ${best.sizeMB.toFixed(1)}MB`);

    // Se em modo duck ou se o quickCheck nao e conclusivo, testar no DuckStation
    let confirmed = false;
    if (duckMode || best.sizeMB < 10) {
      duckTests++;
      console.log(`  Testando no DuckStation: ${best.file}...`);
      confirmed = testDuckStation(path.join(PSX_DIR, best.file));
      console.log(`  -> DuckStation: ${confirmed ? 'OK' : 'FALHOU'}`);
    } else {
      confirmed = true; // confiar no quickCheck
    }

    if (confirmed) {
      // Renomear o melhor para o nome sem (N)
      const cleanName = `${base}.chd`;
      if (main) {
        // Mover principal ruim para duplicados
        moveToDup(main);
        console.log(`  -> Movido principal ruim: ${main}`);
      }
      if (best.file !== cleanName) {
        renameChd(best.file, cleanName);
        console.log(`  -> Renomeado: ${best.file} -> ${cleanName}`);
      }
      // Mover outros duplicados
      for (const c of checks.filter(x => x.file !== main && x.file !== best.file)) {
        moveToDup(c.file);
        console.log(`  -> Movido: ${c.file}`);
      }
      keptDupe++;
      continue;
    }
  }

  // Estrategia 3: nenhum passou no quickCheck - testar no DuckStation um por um
  console.log(`  Nenhum passou no quickCheck - testando no DuckStation...`);
  let found = false;
  for (const c of checks.sort((a, b) => b.sizeMB - a.sizeMB)) {
    duckTests++;
    console.log(`  Testando: ${c.file} (${c.sizeMB.toFixed(1)}MB, ${c.trackCount} trilhas)...`);
    const ok = testDuckStation(path.join(PSX_DIR, c.file));
    console.log(`  -> ${ok ? 'OK' : 'FALHOU'}`);
    if (ok) {
      const cleanName = `${base}.chd`;
      if (c.file !== cleanName) {
        // Mover principal se existir e for diferente
        if (main && main !== c.file) {
          moveToDup(main);
          console.log(`  -> Movido principal: ${main}`);
        }
        renameChd(c.file, cleanName);
        console.log(`  -> Renomeado: ${c.file} -> ${cleanName}`);
      }
      // Mover outros
      for (const other of checks.filter(x => x.file !== c.file)) {
        moveToDup(other.file);
        console.log(`  -> Movido: ${other.file}`);
      }
      found = true;
      keptDupe++;
      break;
    }
  }

  if (!found) {
    console.log(`  TODOS FALHARAM - movendo para duplicados e rebaixando`);
    const serial = extractSerial(base);
    for (const c of checks) {
      moveToDup(c.file);
      console.log(`  -> Movido: ${c.file}`);
    }
    if (serial) {
      addToQueue(serial, base.replace(/-/g, ' '));
      console.log(`  -> Rebaixado: ${serial}`);
    }
    allFailed++;
  }
}

console.log(`\n=== Resumo ===`);
console.log(`Grupos processados: ${processed}`);
console.log(`Principal mantido: ${keptMain}`);
console.log(`Duplicado promovido: ${keptDupe}`);
console.log(`Todos falharam: ${allFailed}`);
console.log(`Testes DuckStation: ${duckTests}`);
