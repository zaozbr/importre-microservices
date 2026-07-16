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
const bins = all.filter(f => /\.(bin|img|iso)$/i.test(f));

// Para cada bin, verificar se o CHD correspondente ja existe
const dirsToClean = new Set();
let deleted = 0, deletedBytes = 0;
const keepBins = new Set();

for (const bin of bins) {
  const base = path.basename(bin, path.extname(bin));
  const dir = path.dirname(bin);
  const s = serial(path.basename(dir)) || serial(base);
  const chdName = s && !serial(base) ? s + '.chd' : base + '.chd';
  const chdKey = chdName.replace(/\.chd$/i, '');

  let isValid = true;
  try { if (fs.statSync(bin).size < 1024 * 1024) isValid = false; } catch { isValid = false; }

  if (main.has(chdKey) || !isValid) {
    // Descartavel: deletar bin + arquivos relacionados (cue, sub, ccd, mds, mdf, etc)
    const baseNoExt = path.basename(bin, path.extname(bin));
    const dir2 = path.dirname(bin);
    const related = all.filter(f => {
      const fb = path.basename(f);
      // Mesmo base name, extensoes relacionadas
      return fb.startsWith(baseNoExt) && /\.(bin|img|iso|cue|sub|ccd|mds|mdf|ape|7z)$/i.test(f);
    });
    for (const f of related) {
      try {
        const sz = fs.statSync(f).size;
        fs.unlinkSync(f);
        deleted++;
        deletedBytes += sz;
      } catch {}
    }
    dirsToClean.add(dir2);
  } else {
    keepBins.add(bin);
  }
}

console.log(`Bins descartaveis deletados: ${deleted} arquivos (${(deletedBytes / 1073741824).toFixed(2)} GB)`);
console.log(`Bins mantidos (aproveitaveis): ${keepBins.size}`);

// Limpar pastas vazias
function rmEmpty(dir) {
  let n = 0;
  try {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      if (e.isDirectory()) {
        const sub = path.join(dir, e.name);
        n += rmEmpty(sub);
        try { if (fs.readdirSync(sub).length === 0) { fs.rmdirSync(sub); n++; } } catch {}
      }
    }
  } catch {}
  return n;
}
const cleaned = rmEmpty(DUP);
console.log(`Pastas vazias removidas: ${cleaned}`);
console.log(`Arquivos restantes em duplicados: ${walk(DUP).length}`);
