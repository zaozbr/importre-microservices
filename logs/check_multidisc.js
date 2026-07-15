const fs = require('fs');
const QUEUE_PATH = 'F:\\importre_state\\queue.json';
const q = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
// Procurar seriais que comecam com SLPS-00006, SLPS-01966, etc.
const bases = ['SLPS-00006', 'SLPS-01966', 'SLPS-02847', 'SLUS-00757', 'SLUS-00900', 'SLUS-01561'];
for (const b of bases) {
  const found = (q.queue || []).filter(i => i.serial && i.serial.startsWith(b));
  console.log(`${b}: ${found.length} entradas -> ${found.map(f => f.serial + '(' + f.status + ')').join(', ')}`);
}
