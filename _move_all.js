const fs = require('fs');
const path = require('path');

const PSX_DIR = 'D:\\roms\\library\\roms\\PSX';
const DUP_DIR = 'D:\\roms\\duplicados';

if (!fs.existsSync(DUP_DIR)) fs.mkdirSync(DUP_DIR, { recursive: true });

const allFiles = fs.readdirSync(PSX_DIR);
let moved = 0, errors = 0, kept = 0;
const errorFiles = [];

for (const f of allFiles) {
  // Mantem apenas .chd e .aria2 (downloads em andamento)
  if (f.endsWith('.chd') || f.endsWith('.aria2')) { kept++; continue; }

  const src = path.join(PSX_DIR, f);
  const dst = path.join(DUP_DIR, f);

  try {
    if (fs.existsSync(dst)) fs.unlinkSync(dst);
    fs.renameSync(src, dst);
    moved++;
  } catch (e) {
    try {
      fs.copyFileSync(src, dst);
      fs.unlinkSync(src);
      moved++;
    } catch (e2) {
      errors++;
      if (errors <= 15) errorFiles.push(f);
    }
  }
}

console.log(`Movidos: ${moved}`);
console.log(`Mantidos (chd/aria2): ${kept}`);
console.log(`Erros: ${errors}`);
if (errorFiles.length) {
  console.log('Erros:');
  errorFiles.forEach(f => console.log('  ' + f));
}

const remaining = fs.readdirSync(PSX_DIR);
console.log(`\nPSX_DIR final: ${remaining.length} arquivos`);
console.log(`  CHD: ${remaining.filter(f => f.endsWith('.chd')).length}`);
console.log(`  aria2: ${remaining.filter(f => f.endsWith('.aria2')).length}`);
console.log(`  outros: ${remaining.filter(f => !f.endsWith('.chd') && !f.endsWith('.aria2')).length}`);
