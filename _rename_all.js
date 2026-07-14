const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PSX_DIR = 'D:\\roms\\library\\roms\\PSX';
const TEMP_DIR = 'F:\\chd_temp';
const CHDMAN = 'F:\\importre\\chdman.exe';

// Limpa temp
function cleanTemp() {
  for (const f of fs.readdirSync(TEMP_DIR)) {
    if (f.startsWith('_extract_')) {
      try { fs.unlinkSync(path.join(TEMP_DIR, f)); } catch (e) { }
    }
  }
}

// Extrai serial do CHD via extracao temporaria
function extractSerial(chdPath) {
  cleanTemp();
  const cuePath = path.join(TEMP_DIR, '_extract.cue');
  const binPath = path.join(TEMP_DIR, '_extract.bin');
  try {
    execSync(`"${CHDMAN}" extractcd -i "${chdPath}" -o "${cuePath}" -ob "${binPath}" -f`, {
      timeout: 120000, stdio: 'pipe', encoding: 'utf8'
    });
  } catch (e) { return null; }

  // Le primeiros 1MB do BIN
  try {
    const fd = fs.openSync(binPath, 'r');
    const buf = Buffer.alloc(1048576);
    fs.readSync(fd, buf, 0, 1048576, 0);
    fs.closeSync(fd);
    const str = buf.toString('latin1');
    const m = str.match(/(SL[UEP]S|SC[UEP]S|SLPM|SLED)-\d{3,5}/i);
    if (m) return m[0].toUpperCase();
  } catch (e) { }

  // Cleanup
  try { fs.unlinkSync(cuePath); } catch (e) { }
  try { fs.unlinkSync(binPath); } catch (e) { }
  return null;
}

// Lista CHDs
const allFiles = fs.readdirSync(PSX_DIR).filter(f => f.endsWith('.chd'));
console.log(`Total CHDs: ${allFiles.length}`);

// Classifica
const noSerial = [];
const withSerial = [];
for (const f of allFiles) {
  const m = f.match(/(SL[UEP]S|SC[UEP]S|SLPM|SLED)-\d{3,5}/i);
  if (m) withSerial.push(f);
  else noSerial.push(f);
}
console.log(`Com serial: ${withSerial.length}`);
console.log(`Sem serial: ${noSerial.length}`);

// Processa os sem serial
let extracted = 0, failed = 0, renamed = 0, renameErrors = 0;
const stillNoSerial = [];

for (let i = 0; i < noSerial.length; i++) {
  const f = noSerial[i];
  const chdPath = path.join(PSX_DIR, f);

  // Extrai serial
  const serial = extractSerial(chdPath);
  if (!serial) {
    failed++;
    stillNoSerial.push(f);
    if (failed <= 5) console.log(`  [${i + 1}/${noSerial.length}] SEM serial: ${f}`);
    continue;
  }

  extracted++;

  // Limpa o nome: remove ext .chd, remove espacos, mantem so o nome do jogo
  let gameName = f.replace(/\.chd$/i, '');
  // Remove caracteres invalidos para nome de arquivo
  gameName = gameName.replace(/[<>:"/\\|?*]/g, '-');
  // Remove espacos e substitui por hifens
  gameName = gameName.replace(/\s+/g, '-');
  // Remove hifens duplicados
  gameName = gameName.replace(/-+/g, '-');
  // Remove hifens no inicio/fim
  gameName = gameName.replace(/^-+|-+$/g, '');

  // Novo nome: nome-do-jogo-SERIAL.chd
  let newName = `${gameName}-${serial}.chd`;

  // Evita nome muito longo (Windows max 260 chars, mas limitamos a 150)
  if (newName.length > 150) {
    newName = `${gameName.substring(0, 150 - serial.length - 6)}-${serial}.chd`;
  }

  const newPath = path.join(PSX_DIR, newName);

  // Se o arquivo ja existe com o novo nome, pula
  if (fs.existsSync(newPath) && newPath !== chdPath) {
    console.log(`  [${i + 1}/${noSerial.length}] JA EXISTE: ${f} -> ${newName}`);
    continue;
  }

  try {
    fs.renameSync(chdPath, newPath);
    renamed++;
    if (i < 10 || (i + 1) % 50 === 0) {
      console.log(`  [${i + 1}/${noSerial.length}] ${f.substring(0, 40)} -> ${newName.substring(0, 60)}`);
    }
  } catch (e) {
    renameErrors++;
    if (renameErrors <= 5) console.log(`  ERRO renomear ${f}: ${e.message}`);
  }
}

// Cleanup temp
cleanTemp();

console.log(`\n=== RESULTADO ===`);
console.log(`Seriais extraidos do header: ${extracted}`);
console.log(`Falharam (sem serial no header): ${failed}`);
console.log(`Renomeados: ${renamed}`);
console.log(`Erros de rename: ${renameErrors}`);
if (stillNoSerial.length > 0) {
  console.log(`\nAinda sem serial (${stillNoSerial.length}):`);
  stillNoSerial.slice(0, 20).forEach(f => console.log(`  ${f}`));
  if (stillNoSerial.length > 20) console.log(`  ... e mais ${stillNoSerial.length - 20}`);
}
