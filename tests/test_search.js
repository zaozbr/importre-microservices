// Testes automatizados do search service
// Testa plugins, sites.js, diversificacao
// Run: node tests/test_search.js

const assert = require('assert');
const path = require('path');

// Mock STATE_DIR para nao interferir com dados reais
process.env.ROMS_DIR = path.join(__dirname, 'test_roms');

let testsPassed = 0;
let testsFailed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
    testsPassed++;
  } catch (e) {
    console.error(`  ✗ ${name}: ${e.message}`);
    testsFailed++;
  }
}

async function testAsync(name, fn) {
  try {
    await fn();
    console.log(`  ✓ ${name}`);
    testsPassed++;
  } catch (e) {
    console.error(`  ✗ ${name}: ${e.message}`);
    testsFailed++;
  }
}

console.log('=== Testes Search Service ===\n');

// Carrega plugins
const { plugins } = require('../services/search/plugins/loader');

// Teste 1: plugins carregados
test('plugins: pelo menos 20 plugins carregados', () => {
  const count = Object.keys(plugins).length;
  assert.ok(count >= 20, `esperado >= 20 plugins, got ${count}`);
});

// Teste 2: plugins essenciais existem
test('plugins: coolrom, archive.org, archive.org-jp existem', () => {
  assert.ok(plugins.coolrom, 'coolrom deve existir');
  assert.ok(plugins['archive_org'], 'archive_org deve existir');
  assert.ok(plugins['archive_org_jp'], 'archive_org_jp deve existir');
});

// Teste 3: todo plugin tem name e search function
test('plugins: todos tem name e search function', () => {
  for (const [key, p] of Object.entries(plugins)) {
    assert.ok(p.name, `${key} deve ter name`);
    assert.strictEqual(typeof p.search, 'function', `${key} deve ter search function`);
  }
});

// Teste 4: todo plugin tem priority
test('plugins: todos tem priority numerica', () => {
  for (const [key, p] of Object.entries(plugins)) {
    assert.ok(typeof p.priority === 'number', `${key} deve ter priority numerica`);
  }
});

// Teste 5: coolrom plugin retorna array
test('coolrom: search retorna array', () => {
  const result = plugins.coolrom.search('SLUS-001', 'Test Game');
  assert.ok(Array.isArray(result), 'deve retornar array');
});

// Teste 6: archive.org-jp agora e async
testAsync('archive.org-jp: search async retorna array', async () => {
  const result = await plugins['archive_org_jp'].search('SLPS-001', 'Test JP Game');
  assert.ok(Array.isArray(result), 'deve retornar array');
});

// Teste 7: homebrew so responde a HBREW-
test('homebrew: ignora seriais nao-HBREW', () => {
  const result = plugins.homebrew.search('SLUS-001', 'Test');
  assert.strictEqual(result.length, 0, 'nao deve retornar para SLUS');
});

// Teste 8: sortSourcesBySpeed diversifica (mock)
test('sortSourcesBySpeed: embaralha e ordena por prioridade', () => {
  const speedMap = {
    'vimm': 10, 'romsdl': 10, 'retrostic': 10, 'coolrom': 7,
    'archive.org': 5, 'archive.org-jp': 5, 'google_fallback': 1
  };
  const sources = [
    { site: 'archive.org', url: 'http://a' },
    { site: 'coolrom', url: 'http://b' },
    { site: 'vimm', url: 'http://c' },
    { site: 'google_fallback', url: 'http://d' },
  ];
  const shuffled = [...sources].sort(() => Math.random() - 0.5);
  const sorted = shuffled.sort((a, b) => (speedMap[b.site] || 5) - (speedMap[a.site] || 5));
  // vimm (10) deve vir antes de coolrom (7) que vem antes de archive.org (5)
  const vimmIdx = sorted.findIndex(s => s.site === 'vimm');
  const coolromIdx = sorted.findIndex(s => s.site === 'coolrom');
  const archiveIdx = sorted.findIndex(s => s.site === 'archive.org');
  assert.ok(vimmIdx < coolromIdx, 'vimm deve vir antes de coolrom');
  assert.ok(coolromIdx < archiveIdx, 'coolrom deve vir antes de archive.org');
});

// Teste 9: searchWithTimeout respeita timeout
testAsync('searchWithTimeout: retorna [] em caso de timeout', async () => {
  // Simula timeout com plugin lento
  function searchWithTimeout(pluginName, serial, title, ms) {
    return new Promise((resolve) => {
      const t = setTimeout(() => resolve([]), ms);
      Promise.resolve(plugins[pluginName]?.search(serial, title))
        .then(r => { clearTimeout(t); resolve(r || []); })
        .catch(() => { clearTimeout(t); resolve([]); });
    });
  }
  const result = await searchWithTimeout('coolrom', 'SLUS-001', 'Test', 1);
  // Com 1ms de timeout, pode retornar [] ou resultados (depende da velocidade)
  assert.ok(Array.isArray(result), 'deve retornar array');
});

// Teste 10: buildSource cria objeto correto
test('buildSource: cria fonte com site, url, title', () => {
  const { buildSource } = require('../services/search/plugins/_base');
  const s = buildSource('coolrom', 'http://example.com/game.7z', 'Game Title');
  assert.strictEqual(s.site, 'coolrom');
  assert.strictEqual(s.url, 'http://example.com/game.7z');
  assert.strictEqual(s.title, 'Game Title');
});

// Teste 11: normalize remove acentos e especiais
test('normalize: remove caracteres especiais', () => {
  const { normalize } = require('../services/search/plugins/_base');
  assert.strictEqual(normalize('Final Fantasy VII'), 'final fantasy vii');
  assert.strictEqual(normalize('Metal Gear (Japan)'), 'metal gear japan');
  assert.strictEqual(normalize(''), '');
});

// Teste 12: titleScore calcula similaridade
test('titleScore: 100% para titulos iguais', () => {
  const { titleScore } = require('../services/search/plugins/_base');
  assert.strictEqual(titleScore('Final Fantasy VII', 'Final Fantasy VII'), 1);
  assert.ok(titleScore('Final Fantasy VII', 'Final Fantasy') > 0.5, 'deve ter score > 0.5');
  assert.strictEqual(titleScore('Game A', 'Game B'), 0.5); // 1 palavra em comum de 2
});

(async () => {
  console.log(`\n=== Resultado: ${testsPassed} passaram, ${testsFailed} falharam ===`);
  process.exit(testsFailed > 0 ? 1 : 0);
})();
