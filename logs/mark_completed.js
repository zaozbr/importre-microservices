const fs = require('fs');

const QUEUE_PATH = 'F:\\importre_state\\queue.json';
const serials = fs.readFileSync('F:\\importre\\logs\\moved_chds.txt', 'utf8')
  .split('\n').map(s => s.trim()).filter(Boolean);

const q = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
const serialSet = new Set(serials);

let completed = 0, notFound = 0;

// Marca items na queue
if (q.queue) {
  for (const item of q.queue) {
    if (serialSet.has(item.serial)) {
      item.status = 'completed';
      item.completed = new Date().toISOString();
      completed++;
    }
  }
}

// Remove de in_progress e failed, move para completed
for (const serial of serials) {
  if (q.in_progress && q.in_progress[serial]) {
    if (!q.completed) q.completed = {};
    q.completed[serial] = q.in_progress[serial];
    delete q.in_progress[serial];
  }
  if (q.failed && q.failed[serial]) {
    delete q.failed[serial];
  }
  if (!q.queue || !q.queue.find(i => i.serial === serial)) {
    notFound++;
  }
}

// Backup
fs.copyFileSync(QUEUE_PATH, QUEUE_PATH + '.bak');

// Salva
fs.writeFileSync(QUEUE_PATH, JSON.stringify(q, null, 2), 'utf-8');

console.log(`Marcados completed: ${completed}`);
console.log(`Nao encontrados na queue: ${notFound}`);
console.log(`Total seriais processados: ${serials.length}`);
