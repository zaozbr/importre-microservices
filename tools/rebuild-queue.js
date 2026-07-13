const fs = require('fs');
const path = require('path');
const { QUEUE_PATH, PSX_DIR } = require('../shared/config');

const FALTANTES = path.join(path.dirname(QUEUE_PATH), '..', 'PSX_Colecao_Faltantes.md');

function extractSerial(name) {
  const m = name.match(/([A-Z]{2,4}[-]\d{3,5})/i);
  return m ? m[1].toUpperCase() : null;
}

const chdSerials = new Set();
for (const f of fs.readdirSync(PSX_DIR)) {
  const s = extractSerial(f);
  if (s) chdSerials.add(s);
}

const titles = {};
const faltantes = new Set();
if (fs.existsSync(FALTANTES)) {
  const content = fs.readFileSync(FALTANTES, 'utf-8');
  let m;
  const re = /([A-Z]{2,4}[-]\d{3,5})/gi;
  while ((m = re.exec(content)) !== null) faltantes.add(m[1].toUpperCase());
  for (const line of content.split('\n')) {
    const m2 = line.match(/^\s*\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|/);
    if (m2) {
      const serial = m2[1].trim().toUpperCase();
      const nome = m2[2].trim();
      if (serial && nome) titles[serial] = nome;
    }
  }
}

const missing = [...faltantes].filter(s => !chdSerials.has(s));

const queue = missing.map(serial => ({
  serial,
  title: titles[serial] || serial,
  status: 'pending',
  priority: 1,
  added: new Date().toISOString(),
  retry_count: 0,
  site_history: {},
  sources: []
}));

const data = {
  queue,
  in_progress: {},
  completed: {},
  failed: {}
};

fs.writeFileSync(QUEUE_PATH, JSON.stringify(data, null, 2), 'utf-8');
console.log(`Faltantes: ${faltantes.size}, ja com CHD: ${chdSerials.size}, adicionados: ${queue.length}`);
