// Testa todos os plugins de busca com seriais reais da fila
// e reporta quais funcionam e quais falham
const fs = require('fs');
const { QUEUE_PATH } = require('../shared/config');

const { plugins } = require('../services/search/plugins/loader');

async function testPlugin(plugin, item) {
  try {
    const result = await Promise.race([
      Promise.resolve(plugin.search(item.serial, item.title)),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout 8s')), 8000))
    ]);
    return { found: Array.isArray(result) && result.length > 0, error: null };
  } catch (e) {
    return { found: false, error: e.message.slice(0, 80) };
  }
}

async function main() {
  const q = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
  const ready = q.queue.filter(i => i.status === 'ready').slice(0, 20);
  const pending = q.queue.filter(i => i.status === 'pending').slice(0, 10);
  const testItems = [...ready, ...pending];

  console.log(`Testando ${testItems.length} itens contra ${Object.keys(plugins).length} plugins\n`);

  const results = {};
  for (const name of Object.keys(plugins)) {
    results[name] = { found: 0, errors: 0, errorSamples: [] };
  }

  for (const item of testItems) {
    for (const [name, plugin] of Object.entries(plugins)) {
      const { found, error } = await testPlugin(plugin, item);
      if (found) results[name].found++;
      if (error) {
        results[name].errors++;
        if (results[name].errorSamples.length < 2) results[name].errorSamples.push(error);
      }
    }
  }

  console.log('=== Resultado por plugin ===\n');
  const sorted = Object.entries(results).sort((a, b) => b[1].found - a[1].found);
  for (const [name, r] of sorted) {
    const status = r.found > 0 ? 'OK' : (r.errors > 0 ? 'ERRO' : 'VAZIO');
    console.log(`  ${name.padEnd(25)} ${status.padEnd(6)} found=${r.found} errors=${r.errors}`);
    for (const s of r.errorSamples) console.log(`    → ${s}`);
  }
}

main().catch(e => { console.error('Erro:', e.message); process.exit(1); });
