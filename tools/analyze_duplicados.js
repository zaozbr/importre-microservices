const fs = require('fs');
const path = require('path');
const DUP = 'D:\\roms\\duplicados';
const ROM = 'D:\\roms\\library\\roms\\psx';
const main = new Set(fs.readdirSync(ROM).filter(f => f.toLowerCase().endsWith('.chd')).map(f => f.replace(/\.chd$/i, '')));

function walk(d) {
  const r = [];
  try {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const f = path.join(d, e.name);
      if (e.isDirectory()) r.push(...walk(f));
      else r.push(f);
    }
  } catch {}
  return r;
}

function serial(n) {
  const m = n.match(/(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}/i);
  if (!m) return null;
  return m[0].toUpperCase().replace('_', '-').replace(/^(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)0*(\d{3,5})$/i, '$1-$2');
}

const all = walk(DUP);
const chds = all.filter(f => f.toLowerCase().endsWith('.chd'));
const bins = all.filter(f => /\.(bin|img|iso)$/i.test(f));
const validBins = bins.filter(b => { try { return fs.statSync(b).size > 1024 * 1024; } catch { return false; } });

let chdUnique = 0, chdDup = 0;
for (const c of chds) {
  const b = path.basename(c, '.chd');
  if (main.has(b)) chdDup++;
  else chdUnique++;
}

let binNew = 0, binDupSerial = 0;
const newChdNames = [];
for (const b of validBins) {
  const base = path.basename(b, path.extname(b));
  const s = serial(path.basename(path.dirname(b))) || serial(base);
  const chdName = s && !serial(base) ? s + '.chd' : base + '.chd';
  const chdKey = chdName.replace(/\.chd$/i, '');
  if (main.has(chdKey)) binDupSerial++;
  else { binNew++; newChdNames.push(chdName); }
}

console.log('=== Duplicados - analise ===');
console.log('CHDs soltos:', chds.length, '(unicos:', chdUnique, 'duplicados:', chdDup, ')');
console.log('Bins validos:', validBins.length, '(gerariam CHD novo:', binNew, 'ja existem:', binDupSerial, ')');
console.log('Total aproveitavel:', chdUnique + binNew);
console.log('CHDs na colecao:', main.size);
console.log('\nAmostra de CHDs novos (primeiros 20):');
newChdNames.slice(0, 20).forEach(n => console.log(' ', n));
