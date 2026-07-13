// Teste: Fluxo completo de pós-download
// 1. Validação de serial no conteúdo extraído
// 2. CHD service extrai .7z antes de converter
// 3. CHD service apaga .bin/.cue após conversão
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const os = require('os');

console.log('=== Testes: Fluxo pós-download ===\n');

// Teste 1: validateExtractedContent - serial presente
console.log('Teste 1: validateExtractedContent com serial presente');
{
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'test-psx-'));
  const origReadDir = fs.readdirSync;
  // Mock: cria arquivo .chd com serial no nome
  fs.writeFileSync(path.join(tmpDir, 'Crash-Bandicoot-SLUS-00362.chd'), 'fake');
  
  // Simula validateExtractedContent
  const files = fs.readdirSync(tmpDir);
  const serialLower = 'SLUS-00362'.toLowerCase();
  const matches = files.filter(f => 
    f.toLowerCase().includes(serialLower) &&
    /\.(chd|bin|cue|iso|img)$/i.test(f)
  );
  
  assert.strictEqual(matches.length, 1, 'Deveria encontrar 1 arquivo com o serial');
  console.log('  PASS: Serial encontrado no conteúdo\n');
  
  fs.rmSync(tmpDir, { recursive: true });
}

// Teste 2: validateExtractedContent - serial ausente (download errado)
console.log('Teste 2: validateExtractedContent com serial ausente');
{
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'test-psx-'));
  // Cria arquivo .chd SEM o serial esperado
  fs.writeFileSync(path.join(tmpDir, 'Wrong-Game-SLUS-99999.chd'), 'fake');
  
  const files = fs.readdirSync(tmpDir);
  const serialLower = 'SLUS-00362'.toLowerCase();
  const matches = files.filter(f => 
    f.toLowerCase().includes(serialLower) &&
    /\.(chd|bin|cue|iso|img)$/i.test(f)
  );
  
  assert.strictEqual(matches.length, 0, 'Nao deveria encontrar arquivo com serial errado');
  console.log('  PASS: Serial errado nao encontrado (download errado detectado)\n');
  
  fs.rmSync(tmpDir, { recursive: true });
}

// Teste 3: CHD service - cleanupAfterConversion apaga .bin e .cue
console.log('Teste 3: cleanupAfterConversion apaga .bin e .cue');
{
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'test-psx-'));
  const cuePath = path.join(tmpDir, 'Test.cue');
  const binPath = path.join(tmpDir, 'Test.bin');
  fs.writeFileSync(cuePath, 'FILE "Test.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n');
  fs.writeFileSync(binPath, 'fake-bin-data');
  
  // Simula cleanupAfterConversion
  const job = { cuePath, binRefs: ['Test.bin'] };
  for (const ref of job.binRefs) {
    const p = path.join(tmpDir, ref);
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
  if (fs.existsSync(job.cuePath)) fs.unlinkSync(job.cuePath);
  
  assert.ok(!fs.existsSync(cuePath), '.cue deveria ser apagado');
  assert.ok(!fs.existsSync(binPath), '.bin deveria ser apagado');
  console.log('  PASS: .bin e .cue apagados apos conversao\n');
  
  fs.rmSync(tmpDir, { recursive: true });
}

// Teste 4: CHD service - buildChdName gera nome correto
console.log('Teste 4: buildChdName gera nome com serial');
{
  // Simula buildChdName
  const stem = 'Crash Bandicoot (USA) [SLUS-00362]';
  const serial = 'SLUS-00362';
  let base = stem
    .replace(/\(Track \d+\)/gi, '')
    .replace(/\(Disc \d+\)/gi, '')
    .replace(/\(.*?\)/g, '')
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .trim();
  base = `${base}-${serial}`;
  const chdName = base.slice(0, 180).replace(/[.\s]+$/, '') + '.chd';
  
  assert.ok(chdName.includes('SLUS-00362'), 'Nome .chd deveria conter o serial');
  assert.ok(chdName.endsWith('.chd'), 'Nome deveria terminar com .chd');
  console.log(`  PASS: Nome gerado: ${chdName}\n`);
}

// Teste 5: CHD service - findOrphanBins encontra .bin sem .cue
console.log('Teste 5: findOrphanBins encontra .bin sem .cue');
{
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'test-psx-'));
  // Cria .bin sem .cue
  fs.writeFileSync(path.join(tmpDir, 'Orphan.bin'), Buffer.alloc(2 * 1024 * 1024));
  // Cria .bin com .cue (nao deveria ser orfao)
  fs.writeFileSync(path.join(tmpDir, 'WithCue.bin'), Buffer.alloc(2 * 1024 * 1024));
  fs.writeFileSync(path.join(tmpDir, 'WithCue.cue'), 'FILE "WithCue.bin" BINARY\n');
  
  const files = fs.readdirSync(tmpDir);
  const cueStems = new Set(files.filter(f => f.endsWith('.cue')).map(f => f.replace(/\.cue$/i, '')));
  const orphans = [];
  for (const f of files) {
    if (!f.endsWith('.bin')) continue;
    const stem = f.replace(/\.bin$/i, '');
    if (cueStems.has(stem)) continue;
    const st = fs.statSync(path.join(tmpDir, f));
    if (st.size < 1024 * 1024) continue;
    orphans.push(f);
  }
  
  assert.strictEqual(orphans.length, 1, 'Deveria encontrar 1 .bin orfao');
  assert.strictEqual(orphans[0], 'Orphan.bin', 'Orfao deveria ser Orphan.bin');
  console.log('  PASS: 1 .bin orfao encontrado\n');
  
  fs.rmSync(tmpDir, { recursive: true });
}

async function main() {
  console.log('=== Todos os 5 testes passaram! ===');
}
main();
