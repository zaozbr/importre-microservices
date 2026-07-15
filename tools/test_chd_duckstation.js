/**
 * Testa CHDs no DuckStation (batch mode) e verifica se bootam corretamente.
 * Uso: node tools/test_chd_duckstation.js
 */
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const DUCK = 'C:\\Users\\Usuario\\AppData\\Local\\Programs\\DuckStation\\duckstation-qt-x64-ReleaseLTCG.exe';
const PSX_DIR = 'D:\\roms\\library\\roms\\psx';
const DUCK_LOG = 'C:\\Users\\Usuario\\Documents\\DuckStation\\duckstation.log';

const chdsToTest = [
  'Yeh-Yeh-Tennis-SLES-02272.chd',
  'Wan-Der-Vehicles-Doggy-Bone-Daisakusen-SLPS-02322.chd',
  'Hiza-No-Ue-No-Partner-Kitty-On-Your-Lap-SLPS-01302.chd',
  'Eisei-Meijin-II-SLPM-86014.chd',
  'Zen-Nihon-GT-Senshuken-SLPS-00716.chd',
  'Actua-Pool-SLES-01647.chd',
];

function testChd(chdName) {
  const chdPath = path.join(PSX_DIR, chdName);
  if (!fs.existsSync(chdPath)) {
    return { chd: chdName, status: 'NOT_FOUND' };
  }

  // Limpar log (tentar deletar, esperar se locked)
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      if (fs.existsSync(DUCK_LOG)) fs.unlinkSync(DUCK_LOG);
      break;
    } catch (e) {
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 2000);
    }
  }

  console.log(`  Testando: ${chdName}...`);

  try {
    // Rodar em batch mode por 30s
    execSync(`"${DUCK}" -batch -fastboot -earlyconsole -- "${chdPath}"`, {
      stdio: 'pipe',
      timeout: 35000,
    });
  } catch (e) {
    // Timeout e esperado (o processo e morto apos 30s)
  }

  // Esperar processo terminar completamente
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 3000);

  // Ler log
  const log = fs.existsSync(DUCK_LOG) ? fs.readFileSync(DUCK_LOG, 'utf8') : '';

  // Analisar
  const hasBoot = log.includes('System booted');
  const hasRegion = log.match(/Auto-detected console (\S+) region/);
  const region = hasRegion ? hasRegion[1] : 'unknown';
  const hasAudio = log.includes('Cubeb') || log.includes('audio stream');
  const hasError = log.includes('ERROR') || log.includes('Fatal');
  const hasNonPS1 = log.includes('Non-PS1');

  const status = hasBoot ? 'OK' : (hasNonPS1 ? 'NON-PS1' : (hasError ? 'ERROR' : 'UNKNOWN'));

  return {
    chd: chdName,
    status,
    region,
    hasAudio,
    hasError,
    logLines: log.split('\n').length,
  };
}

// === Main ===
console.log('=== Teste de CHDs no DuckStation ===\n');
const results = [];

for (const chd of chdsToTest) {
  const result = testChd(chd);
  results.push(result);
  console.log(`  -> ${result.status} | regiao: ${result.region} | audio: ${result.hasAudio} | erro: ${result.hasError}`);
}

console.log('\n=== Resultado ===');
console.log('CHD'.padEnd(55) + 'Status'.padEnd(10) + 'Regiao'.padEnd(10) + 'Audio'.padEnd(8) + 'Erro');
console.log('-'.repeat(90));
for (const r of results) {
  console.log(
    r.chd.padEnd(55) +
    r.status.padEnd(10) +
    r.region.padEnd(10) +
    String(r.hasAudio).padEnd(8) +
    String(r.hasError)
  );
}
