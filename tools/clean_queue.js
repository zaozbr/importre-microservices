const fs = require('fs');

const QUEUE_PATH = 'F:\\importre_state\\queue.json';
const ROM_DIR = 'D:\\roms\\library\\roms\\psx';

function extractSerial(name) {
  const m = name.match(/(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}/i);
  if (!m) return null;
  return m[0].toUpperCase().replace('_', '-').replace(/^(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)0*(\d{3,5})$/i, '$1-$2');
}

function norm(s) { return s.toLowerCase().replace(/[^a-z0-9]/g, ''); }

// Ler colecao
const colChds = fs.readdirSync(ROM_DIR).filter(f => f.toLowerCase().endsWith('.chd'));
const colSerials = new Set();
const colNorms = new Set();
for (const f of colChds) {
  const s = extractSerial(f);
  if (s) colSerials.add(s);
  colNorms.add(norm(f.replace(/\.chd$/i, '')));
}
console.log('CHDs na colecao:', colChds.length);

// Ler queue
const queue = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
const before = queue.queue.length;
console.log('Queue antes:', before);

// Filtrar itens que ja existem na colecao
const removed = [];
queue.queue = queue.queue.filter(item => {
  const { serial, title } = item;
  // Check por serial
  if (serial && colSerials.has(serial)) {
    removed.push({ serial, title, reason: 'serial na colecao' });
    return false;
  }
  // Check por nome normalizado
  if (title && colNorms.has(norm(title))) {
    removed.push({ serial, title, reason: 'nome na colecao' });
    return false;
  }
  // Check por serial normalizado
  if (serial && colNorms.has(norm(serial))) {
    removed.push({ serial, title, reason: 'serial norm na colecao' });
    return false;
  }
  return true;
});

const after = queue.queue.length;
console.log('Removidos:', before - after);
console.log('Queue depois:', after);

if (removed.length > 0) {
  console.log('\nItens removidos:');
  removed.forEach(r => console.log(`  [${r.reason}] ${r.serial} - ${r.title}`));
  // Salvar
  fs.copyFileSync(QUEUE_PATH, QUEUE_PATH + '.bak');
  fs.writeFileSync(QUEUE_PATH, JSON.stringify(queue, null, 2));
  console.log('\nQueue salva.');
}

// Estatisticas por status
const byStatus = {};
for (const item of queue.queue) {
  byStatus[item.status] = (byStatus[item.status] || 0) + 1;
}
console.log('\nStatus da queue:');
for (const [s, c] of Object.entries(byStatus)) console.log(`  ${s}: ${c}`);
