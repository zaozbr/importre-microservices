const fs = require('fs');
const path = require('path');
const { QUEUE_PATH, ROMS_DIR } = require('../shared/config');

const FALTANTES_PATH = path.join(ROMS_DIR, 'PSX_Colecao_Faltantes.md');

function loadQueue() {
  if (!fs.existsSync(QUEUE_PATH)) return { queue: [] };
  return JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
}

function saveQueue(data) {
  fs.writeFileSync(QUEUE_PATH, JSON.stringify(data, null, 2), 'utf-8');
}

function parseFaltantes() {
  const map = {};
  if (!fs.existsSync(FALTANTES_PATH)) {
    console.log('Arquivo nao encontrado:', FALTANTES_PATH);
    return map;
  }
  const content = fs.readFileSync(FALTANTES_PATH, 'utf-8');
  const lines = content.split('\n');
  for (const line of lines) {
    const m = line.match(/^\s*\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|/);
    if (m) {
      const serial = m[1].trim();
      const nome = m[2].trim();
      if (serial && nome) map[serial] = nome;
    }
  }
  return map;
}

function main() {
  const q = loadQueue();
  const titles = parseFaltantes();
  let filled = 0;
  for (const item of q.queue) {
    if (!item.title || item.title === item.serial) {
      const t = titles[item.serial];
      if (t) {
        item.title = t;
        filled++;
      }
    }
  }
  saveQueue(q);
  console.log(`Titulos preenchidos: ${filled}`);
  console.log(`Total na fila: ${q.queue.length}`);
}

main();
