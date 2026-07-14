/**
 * _rename_fast.js — Renomeia CHDs sem serial extraindo apenas o primeiro hunk
 * Estrategia: chdman extractcd extrai só o inicio do BIN (setor de boot tem o serial)
 * Otimizacao: extrai para F:\chd_temp (SSD) e le apenas primeiros 256KB do BIN
 */
const fs = require('fs');
const path = require('path');
const { execSync, spawnSync } = require('child_process');

const PSX_DIR = 'D:\\roms\\library\\roms\\PSX';
const TEMP_DIR = 'F:\\chd_temp';
const CHDMAN = 'F:\\importre\\chdman.exe';
const SERIAL_RE = /(SL[UEP]S|SC[UEP]S|SLPM|SLED)-\d{3,5}/i;

// Extrai serial lendo o header do CHD via extracao temporaria
function extractSerial(chdPath) {
  const cuePath = path.join(TEMP_DIR, '_rn.cue');
  const binPath = path.join(TEMP_DIR, '_rn.bin');
  // Remove arquivos temp anteriores
  try { fs.unlinkSync(cuePath); } catch (e) {}
  try { fs.unlinkSync(binPath); } catch (e) {}

  try {
    // Extrai - usa -f para forcar sobrescrita
    // Como chdman nao tem opcao de extrair parcial, vamos extrair e interromper cedo
    // Mas na verdade, extrair e ler os primeiros bytes e rapido no SSD
    const result = spawnSync(CHDMAN, ['extractcd', '-i', chdPath, '-o', cuePath, '-ob', binPath, '-f'], {
      timeout: 180000,
      stdio: 'pipe',
      encoding: 'utf8',
      cwd: TEMP_DIR
    });
    if (result.status !== 0) return null;
  } catch (e) {
    return null;
  }

  // Le apenas primeiros 256KB do BIN
  let serial = null;
  try {
    const fd = fs.openSync(binPath, 'r');
    const buf = Buffer.alloc(262144); // 256KB
    fs.readSync(fd, buf, 0, 262144, 0);
    fs.closeSync(fd);
    const str = buf.toString('latin1');
    const m = str.match(SERIAL_RE);
    if (m) serial = m[0].toUpperCase();
  } catch (e) {}

  // Cleanup
  try { fs.unlinkSync(cuePath); } catch (e) {}
  try { fs.unlinkSync(binPath); } catch (e) {}

  return serial;
}

// Lista CHDs
const allFiles = fs.readdirSync(PSX_DIR).filter(f => f.endsWith('.chd'));
const noSerial = allFiles.filter(f => !SERIAL_RE.test(f));
const withSerial = allFiles.filter(f => SERIAL_RE.test(f));

console.log(`Total CHDs: ${allFiles.length}`);
console.log(`Com serial: ${withSerial.length}`);
console.log(`Sem serial: ${noSerial.length}`);
console.log(`Iniciando extracao de seriais...\n`);

let extracted = 0, failed = 0, renamed = 0, errors = 0;
const stillNoSerial = [];
const startTime = Date.now();

for (let i = 0; i < noSerial.length; i++) {
  const f = noSerial[i];
  const chdPath = path.join(PSX_DIR, f);

  const serial = extractSerial(chdPath);

  if (!serial) {
    failed++;
    stillNoSerial.push(f);
    if (failed <= 10) console.log(`  [${i + 1}/${noSerial.length}] SEM serial: ${f}`);
    continue;
  }

  extracted++;

  // Limpa nome do jogo
  let gameName = f.replace(/\.chd$/i, '');
  gameName = gameName.replace(/[<>:"/\\|?*]/g, '-');
  gameName = gameName.replace(/\s+/g, '-');
  gameName = gameName.replace(/-+/g, '-');
  gameName = gameName.replace(/^-+|-+$/g, '');

  // Novo nome: nome-do-jogo-SERIAL.chd
  let newName = `${gameName}-${serial}.chd`;
  if (newName.length > 150) {
    newName = `${gameName.substring(0, 150 - serial.length - 6)}-${serial}.chd`;
  }

  const newPath = path.join(PSX_DIR, newName);

  if (fs.existsSync(newPath) && newPath.toLowerCase() !== chdPath.toLowerCase()) {
    // Ja existe - adiciona sufixo
    const base = newName.replace(/\.chd$/i, '');
    newName = `${base}_2.chd`;
  }

  try {
    fs.renameSync(chdPath, path.join(PSX_DIR, newName));
    renamed++;
    if (i < 10 || (i + 1) % 25 === 0) {
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);
      const rate = ((i + 1) / (elapsed || 1)).toFixed(1);
      console.log(`  [${i + 1}/${noSerial.length}] ${rate}/s | ${f.substring(0, 35)} -> ${newName.substring(0, 55)}`);
    }
  } catch (e) {
    errors++;
    if (errors <= 5) console.log(`  ERRO: ${f} -> ${e.message}`);
  }
}

const elapsedTotal = ((Date.now() - startTime) / 1000).toFixed(0);
console.log(`\n=== RESULTADO (${elapsedTotal}s) ===`);
console.log(`Seriais extraidos: ${extracted}`);
console.log(`Sem serial no header: ${failed}`);
console.log(`Renomeados: ${renamed}`);
console.log(`Erros: ${errors}`);
if (stillNoSerial.length > 0) {
  console.log(`\nSem serial (${stillNoSerial.length}):`);
  stillNoSerial.slice(0, 30).forEach(f => console.log(`  ${f}`));
  if (stillNoSerial.length > 30) console.log(`  ... e mais ${stillNoSerial.length - 30}`);
}
