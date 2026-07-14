const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PSX_DIR = 'D:\\roms\\library\\roms\\PSX';
const CHDMAN = 'F:\\importre\\chdman.exe';

const allFiles = fs.readdirSync(PSX_DIR).filter(f => f.endsWith('.chd'));

// Classifica arquivos
const withSerial = [];   // ja tem serial no nome
const noSerial = [];     // precisa extrair do header

for (const f of allFiles) {
  // Padrões de serial: SLUS-01234, SLES-01234, SLPS-01234, SLPM-86123, SCPS-10012, SCES-01234, SCUS-94123, SLED-01234, SLPM-80643
  const serialMatch = f.match(/(SL[UEP]S|SC[UEP]S|SLPM|SLED)-\d{3,5}/i);
  if (serialMatch) {
    withSerial.push(f);
  } else {
    noSerial.push(f);
  }
}

console.log(`Total CHDs: ${allFiles.length}`);
console.log(`Com serial no nome: ${withSerial.length}`);
console.log(`Sem serial no nome: ${noSerial.length}`);
console.log('\nSem serial (primeiros 40):');
noSerial.slice(0, 40).forEach(f => console.log('  ' + f));
if (noSerial.length > 40) console.log(`  ... e mais ${noSerial.length - 40}`);
