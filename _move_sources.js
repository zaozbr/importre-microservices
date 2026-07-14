const fs = require('fs');
const path = require('path');

const PSX_DIR = 'D:\\roms\\library\\roms\\PSX';
const DUP_DIR = 'D:\\roms\\duplicados';

if (!fs.existsSync(DUP_DIR)) fs.mkdirSync(DUP_DIR, { recursive: true });

const allFiles = fs.readdirSync(PSX_DIR);
const sourceExts = /\.(bin|cue|iso|7z|zip|rar|img|ccd|sub)$/;

let moved = 0, errors = 0, skipped = 0;
const errorFiles = [];

for (const f of allFiles) {
  if (f.endsWith('.chd') || f.endsWith('.aria2')) { skipped++; continue; }
  if (!sourceExts.test(f)) { skipped++; continue; }

  const src = path.join(PSX_DIR, f);
  const dst = path.join(DUP_DIR, f);

  try {
    if (fs.existsSync(dst)) fs.unlinkSync(dst);
    fs.renameSync(src, dst);
    moved++;
  } catch (e) {
    // Arquivo em uso - copia e deleta
    try {
      fs.copyFileSync(src, dst);
      fs.unlinkSync(src);
      moved++;
    } catch (e2) {
      errors++;
      if (errors <= 10) errorFiles.push(f);
    }
  }
}

console.log(`Movidos: ${moved}`);
console.log(`Pulados (chd/aria2/outros): ${skipped}`);
console.log(`Erros: ${errors}`);
if (errorFiles.length) {
  console.log('Arquivos com erro:');
  errorFiles.forEach(f => console.log('  ' + f));
}

// Relatorio final
const remaining = fs.readdirSync(PSX_DIR);
const dupFiles = fs.readdirSync(DUP_DIR);
console.log(`\nPSX_DIR: ${remaining.length} arquivos`);
console.log(`  CHD: ${remaining.filter(f => f.endsWith('.chd')).length}`);
console.log(`  aria2: ${remaining.filter(f => f.endsWith('.aria2')).length}`);
console.log(`  outros: ${remaining.filter(f => !f.endsWith('.chd') && !f.endsWith('.aria2')).length}`);
console.log(`DUPLICADOS: ${dupFiles.length} arquivos`);
