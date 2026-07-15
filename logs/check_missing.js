const fs = require('fs');
const QUEUE_PATH = 'F:\\importre_state\\queue.json';
const serials = fs.readFileSync('F:\\importre\\logs\\moved_chds.txt', 'utf8')
  .split('\n').map(s => s.trim()).filter(Boolean);
const q = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
const inQueue = new Set((q.queue || []).map(i => i.serial));
const missing = serials.filter(s => !inQueue.has(s));
console.log('Seriais nao encontrados na queue:');
missing.forEach(s => console.log('  ' + s));
