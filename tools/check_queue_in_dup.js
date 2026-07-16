const fs = require('fs');
const path = require('path');

const QUEUE_PATH = 'F:\\importre_state\\queue.json';
const DUP_DIR = 'D:\\roms\\duplicados';
const ROM_DIR = 'D:\\roms\\library\\roms\\psx';

function extractSerial(name) {
  const m = name.match(/(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}/i);
  if (!m) return null;
  return m[0].toUpperCase().replace('_', '-').replace(/^(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)0*(\d{3,5})$/i, '$1-$2');
}

function norm(s) { return s.toLowerCase().replace(/[^a-z0-9]/g, ''); }

// Ler queue
const queue = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
const pending = queue.queue.filter(i => i.status === 'pending');
console.log('Queue total:', queue.queue.length, '| Pending:', pending.length);

// Indexar D:\roms\duplicados por serial e por nome normalizado
function walkDir(dir) {
  const r = [];
  try {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const f = path.join(dir, e.name);
      if (e.isDirectory()) r.push(...walkDir(f));
      else r.push(f);
    }
  } catch {}
  return r;
}

const dupFiles = walkDir(DUP_DIR);
console.log('Arquivos em duplicados:', dupFiles.length);

// Map: serial -> [arquivos]
const dupBySerial = new Map();
// Map: nome normalizado -> [arquivos]
const dupByNorm = new Map();

for (const f of dupFiles) {
  const basename = path.basename(f);
  const serial = extractSerial(basename) || extractSerial(path.basename(path.dirname(f)));
  if (serial) {
    if (!dupBySerial.has(serial)) dupBySerial.set(serial, []);
    dupBySerial.get(serial).push(f);
  }
  const n = norm(basename.replace(/\.(chd|bin|img|iso|cue|sub|ccd|mds|mdf)$/i, ''));
  if (!dupByNorm.has(n)) dupByNorm.set(n, []);
  dupByNorm.get(n).push(f);
}

// Tambem indexar a colecao atual (para nao sugerir o que ja temos)
const colChds = fs.readdirSync(ROM_DIR).filter(f => f.toLowerCase().endsWith('.chd'));
const colSerials = new Set();
for (const f of colChds) {
  const s = extractSerial(f);
  if (s) colSerials.add(s);
}
console.log('CHDs na colecao:', colChds.length);

// Verificar cada item pending da queue
const found = [];
const notFound = [];

for (const item of pending) {
  const { serial, title } = item;

  // 1. Match por serial exato
  if (serial && dupBySerial.has(serial)) {
    const files = dupBySerial.get(serial);
    // Verificar se ja existe na colecao com mesmo serial
    if (colSerials.has(serial)) {
      // Ja temos - nao precisa
      continue;
    }
    found.push({ serial, title, source: 'serial', files });
    continue;
  }

  // 2. Match por nome normalizado
  const n = norm(title || serial || '');
  if (n && dupByNorm.has(n)) {
    const files = dupByNorm.get(n);
    found.push({ serial, title, source: 'name', files });
    continue;
  }

  // 3. Match fuzzy - procurar no dupBySerial por serial parcial
  if (serial) {
    let matched = null;
    for (const [s, files] of dupBySerial) {
      if (s === serial || norm(s) === norm(serial)) {
        matched = files;
        break;
      }
    }
    if (matched) {
      found.push({ serial, title, source: 'serial-fuzzy', files: matched });
      continue;
    }
  }

  notFound.push({ serial, title });
}

console.log('\n=== Resultado ===');
console.log('Encontrados em duplicados:', found.length);
console.log('Nao encontrados:', notFound.length);

if (found.length > 0) {
  console.log('\n=== Encontrados ===');
  for (const f of found) {
    console.log(`  [${f.source}] ${f.serial} - ${f.title}`);
    f.files.slice(0, 3).forEach(file => console.log(`    -> ${path.basename(file)}`));
  }
}

// Salvar relatorio
const report = `Encontrados em duplicados: ${found.length}\nNao encontrados: ${notFound.length}\n\n` +
  found.map(f => `[${f.source}] ${f.serial} - ${f.title}\n  ${f.files.map(file => path.basename(file)).join('\n  ')}`).join('\n');
fs.writeFileSync('F:\\importre\\tools\\queue_in_dup.txt', report);
console.log('\nRelatorio salvo em F:\\importre\\tools\\queue_in_dup.txt');
