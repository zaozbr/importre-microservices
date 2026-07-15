const fs = require('fs');
const QUEUE_PATH = 'F:\\importre_state\\queue.json';
const q = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
const bases = ['SLPS-00006', 'SLPS-01966', 'SLPS-02847'];
let count = 0;
for (const item of q.queue) {
  if (bases.includes(item.serial)) {
    item.status = 'completed';
    item.completed = new Date().toISOString();
    count++;
    console.log(`Marcado: ${item.serial}`);
  }
}
fs.copyFileSync(QUEUE_PATH, QUEUE_PATH + '.bak');
fs.writeFileSync(QUEUE_PATH, JSON.stringify(q, null, 2), 'utf-8');
console.log(`Total: ${count} marcados`);
