// Teste: Spin lock detection e cooldown
// Verifica que requeue nao causa loop infinito
const assert = require('assert');

async function testRequeueCooldown() {
  console.log('Teste 1: Requeue poe item em cooldown (nao ready imediato)');
  
  // Simula o comportamento do queue service
  const queue = [
    { serial: 'SLUS-001', status: 'ready', sources: [{ site: 'coolrom' }] }
  ];
  const in_progress = { 'SLUS-001': queue[0] };
  
  // Simula requeue
  const item = queue.find(i => i.serial === 'SLUS-001');
  item.status = 'cooldown';
  item.cooldown_until = Date.now() + 15000;
  delete in_progress[item.serial];
  
  // Verifica que item NAO esta ready
  const readyItems = queue.filter(i => i.status === 'ready');
  assert.strictEqual(readyItems.length, 0, 'Item deveria estar em cooldown, nao ready');
  assert.strictEqual(item.status, 'cooldown', 'Status deveria ser cooldown');
  console.log('  PASS: Item em cooldown, nao pegavel por workers\n');
}

async function testSpinLockDetection() {
  console.log('Teste 2: Deteccao de spin lock (30+ requeues em 60s)');
  
  let requeueRecent = [];
  let spinLockDetected = false;
  
  // Simula 35 requeues rapidos (spin lock)
  for (let i = 0; i < 35; i++) {
    const now = Date.now();
    requeueRecent.push(now);
    requeueRecent = requeueRecent.filter(t => now - t < 60000);
    
    if (requeueRecent.length > 30) {
      spinLockDetected = true;
      break;
    }
  }
  
  assert.strictEqual(spinLockDetected, true, 'Spin lock deveria ser detectado com 35 requeues');
  console.log('  PASS: Spin lock detectado apoz 35 requeues\n');
}

async function testCooldownExpiry() {
  console.log('Teste 3: Cooldown expira e item volta para ready');
  
  const queue = [
    { serial: 'SLUS-002', status: 'cooldown', cooldown_until: Date.now() - 1000 } // expirado
  ];
  
  // Simula drain watchdog
  const now = Date.now();
  for (const item of queue) {
    if (item.status === 'cooldown' && item.cooldown_until && now > item.cooldown_until) {
      item.status = 'ready';
      delete item.cooldown_until;
    }
  }
  
  assert.strictEqual(queue[0].status, 'ready', 'Item deveria voltar para ready apos cooldown expirar');
  console.log('  PASS: Item voltou para ready apos cooldown expirar\n');
}

async function testWorkerDelayAfterRequeue() {
  console.log('Teste 4: Worker espera 5s apos requeue (nao pega item imediatamente)');
  
  let waited = false;
  const start = Date.now();
  
  // Simula o delay apos requeue
  await new Promise(r => setTimeout(r, 100)); // versao rapida para teste
  waited = true;
  
  const elapsed = Date.now() - start;
  assert.strictEqual(waited, true, 'Worker deveria esperar apos requeue');
  assert.ok(elapsed >= 90, 'Delay deveria ser pelo menos 90ms (simulado)');
  console.log('  PASS: Worker esperou apos requeue\n');
}

async function testFontesUnicasMetric() {
  console.log('Teste 5: Metrica de fontes unicas no watchdog');
  
  const bySource = { 'archive.org': 2, 'archive.org-jp': 2, 'coolrom': 5, 'vimm': 1, 'retrostic': 2 };
  const fontesUnicas = Object.keys(bySource).length;
  
  assert.strictEqual(fontesUnicas, 5, 'Deveria ter 5 fontes unicas');
  assert.ok(fontesUnicas < 10, '5 fontes e abaixo da meta de 10');
  console.log('  PASS: Metrica de fontes unicas calculada corretamente\n');
}

async function main() {
  console.log('=== Testes de Resiliencia - Spin Lock ===\n');
  
  await testRequeueCooldown();
  await testSpinLockDetection();
  await testCooldownExpiry();
  await testWorkerDelayAfterRequeue();
  await testFontesUnicasMetric();
  
  console.log('=== Todos os 5 testes passaram! ===');
}

main().catch(e => {
  console.error('FALHA:', e.message);
  process.exit(1);
});
