const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PSX_DIR = 'D:\\roms\\library\\roms\\PSX';
const DUP_DIR = 'D:\\roms\\duplicados';
const CHDMAN = 'F:\\importre\\chdman.exe';

// 1. Cria D:\roms\duplicados se nao existir
if (!fs.existsSync(DUP_DIR)) {
  fs.mkdirSync(DUP_DIR, { recursive: true });
  console.log('Criado:', DUP_DIR);
}

// 2. Lista todos os arquivos
const allFiles = fs.readdirSync(PSX_DIR);
console.log(`Total arquivos no PSX: ${allFiles.length}`);

// 3. Identifica seriais que ja tem CHD
const chdSerials = new Set();
for (const f of allFiles) {
  if (f.endsWith('.chd')) {
    const m = f.match(/^([A-Z]+-\d{3,5})/);
    if (m) chdSerials.add(m[1]);
    // Tambem verifica padrão _nome-SERIAL.chd
    const m2 = f.match(/([A-Z]+-\d{3,5})\./);
    if (m2) chdSerials.add(m2[1]);
  }
}
console.log(`Seriais com CHD: ${chdSerials.size}`);

// 4. Converte SCPS-10015.bin (unico sem CHD)
const scpsBin = path.join(PSX_DIR, 'SCPS-10015.bin');
const scpsCue = path.join(PSX_DIR, 'SCPS-10015.cue');
const scpsChd = path.join(PSX_DIR, 'SCPS-10015.chd');

if (fs.existsSync(scpsBin) && !fs.existsSync(scpsChd)) {
  console.log('\n--- CONVERTENDO SCPS-10015 ---');
  // Cria CUE basico
  const cueContent = `FILE "SCPS-10015.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`;
  fs.writeFileSync(scpsCue, cueContent);
  console.log('CUE criado:', scpsCue);
  try {
    const out = execSync(`"${CHDMAN}" createcd -i "${scpsChd}" -o "${scpsCue}" --force`, {
      cwd: PSX_DIR,
      timeout: 120000,
      encoding: 'utf8',
      stdio: 'pipe'
    });
    console.log('Conversao OK:', scpsChd);
    chdSerials.add('SCPS-10015');
  } catch (e) {
    console.log('Erro na conversao:', e.message);
    // Tenta sem CUE, apenas bin
    try {
      const out2 = execSync(`"${CHDMAN}" createcd -i "${scpsChd}" -o "${scpsBin}" --force`, {
        cwd: PSX_DIR,
        timeout: 120000,
        encoding: 'utf8',
        stdio: 'pipe'
      });
      console.log('Conversao direta BIN OK:', scpsChd);
      chdSerials.add('SCPS-10015');
    } catch (e2) {
      console.log('Erro conversao direta:', e2.message);
    }
  }
}

// 5. Move arquivos-fonte (bin/cue/iso/7z/zip/rar) para duplicados
// Apenas se o serial ja tem CHD
const sourceExts = /\.(bin|cue|iso|7z|zip|rar|img|ccd|sub)$/;
let moved = 0;
let skipped = 0;
let errors = 0;

for (const f of allFiles) {
  if (f.endsWith('.chd') || f.endsWith('.aria2')) continue;
  if (!sourceExts.test(f)) continue;

  // Extrai serial
  const m = f.match(/^([A-Z]+-\d{3,5})/);
  if (!m) {
    // Sem serial no nome - pula (pode ser arquivo temporario)
    continue;
  }
  const serial = m[1];

  // So move se ja tem CHD
  if (!chdSerials.has(serial)) {
    skipped++;
    continue;
  }

  // Move para duplicados
  const src = path.join(PSX_DIR, f);
  const dst = path.join(DUP_DIR, f);
  try {
    // Se ja existe no destino, remove
    if (fs.existsSync(dst)) {
      fs.unlinkSync(dst);
    }
    fs.renameSync(src, dst);
    moved++;
  } catch (e) {
    // Se falhar (arquivo em uso), copia e deleta
    try {
      fs.copyFileSync(src, dst);
      fs.unlinkSync(src);
      moved++;
    } catch (e2) {
      errors++;
      if (errors <= 5) console.log(`  Erro mover ${f}: ${e2.message}`);
    }
  }
}

console.log(`\n--- MOVER FONTES PARA DUPLICADOS ---`);
console.log(`  Movidos: ${moved}`);
console.log(`  Pulados (sem CHD): ${skipped}`);
console.log(`  Erros: ${errors}`);

// 6. Relatorio final
const remainingFiles = fs.readdirSync(PSX_DIR);
const remainingChd = remainingFiles.filter(f => f.endsWith('.chd'));
const remainingBin = remainingFiles.filter(f => f.endsWith('.bin'));
const remainingCue = remainingFiles.filter(f => f.endsWith('.cue'));
const remainingAria2 = remainingFiles.filter(f => f.endsWith('.aria2'));
const remainingArchives = remainingFiles.filter(f => /\.(7z|zip|rar)$/.test(f));

console.log(`\n--- RESULTADO FINAL ---`);
console.log(`  PSX_DIR: ${remainingFiles.length} arquivos`);
console.log(`    CHD: ${remainingChd.length}`);
console.log(`    BIN: ${remainingBin.length}`);
console.log(`    CUE: ${remainingCue.length}`);
console.log(`    7z/zip/rar: ${remainingArchives.length}`);
console.log(`    aria2 (incompletos): ${remainingAria2.length}`);
console.log(`  DUPLICADOS: ${fs.readdirSync(DUP_DIR).length} arquivos`);
