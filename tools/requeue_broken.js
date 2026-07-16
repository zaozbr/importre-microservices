const fs = require('fs');

const BROKEN_DIR = 'D:\\roms\\psx-quebrados';
const QUEUE_PATH = 'F:\\importre_state\\queue.json';

function extractSerial(name) {
  const m = name.match(/(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}/i);
  if (!m) return null;
  return m[0].toUpperCase().replace('_', '-').replace(/^(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)0*(\d{3,5})$/i, '$1-$2');
}

// Ler CHDs quebrados
const brokenChds = fs.readdirSync(BROKEN_DIR).filter(f => f.toLowerCase().endsWith('.chd'));
console.log('CHDs quebrados:', brokenChds.length);

// Extrair serial e titulo de cada um
const toAdd = [];
for (const f of brokenChds) {
  const base = f.replace(/\.chd$/i, '');
  const serial = extractSerial(base);
  if (serial) {
    toAdd.push({ serial, title: base, file: f });
  } else {
    // Sem serial - usar nome como serial
    console.log('  [SEM SERIAL] ' + f);
    toAdd.push({ serial: base.substring(0, 60), title: base, file: f });
  }
}

console.log('Itens para adicionar na queue:', toAdd.length);

// Ler queue atual
const queue = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
console.log('Queue atual:', queue.queue.length, 'itens');

// Verificar quais ja existem na queue
const existingSerials = new Set(queue.queue.map(i => i.serial));
let added = 0, skipped = 0;
for (const item of toAdd) {
  if (existingSerials.has(item.serial)) {
    skipped++;
    continue;
  }
  queue.queue.push({
    serial: item.serial,
    title: item.title,
    status: 'pending',
    priority: 1,
    added: new Date().toISOString(),
    retry_count: 0,
    site_history: {},
    sources: []
  });
  existingSerials.add(item.serial);
  added++;
}

console.log('Adicionados:', added);
console.log('Ja existiam:', skipped);
console.log('Queue final:', queue.queue.length, 'itens');

// Salvar
fs.copyFileSync(QUEUE_PATH, QUEUE_PATH + '.bak');
fs.writeFileSync(QUEUE_PATH, JSON.stringify(queue, null, 2));
console.log('Queue salva em', QUEUE_PATH);
