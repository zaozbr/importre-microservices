/**
 * _source_hunter.js — Agente perpetuo que busca e integra novas fontes de download
 * Ciclos de 10 minutos por 10 horas (60 ciclos)
 * Estrategia:
 *   1. Verifica fila pendente
 *   2. Busca novas colecoes archive.org (Redump, NoIntro, etc)
 *   3. Tenta criar plugins para sites ROM candidatos
 *   4. Testa plugins com seriais conhecidos
 *   5. Integra plugins funcionais
 *   6. Reinicia servicos
 *   7. Loga progresso
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const axios = require('axios');

const ROOT = 'F:\\importre';
const PLUGINS_DIR = path.join(ROOT, 'services', 'search', 'plugins');
const LOG_FILE = path.join(ROOT, '_source_hunter.log');
const STATE_FILE = path.join(ROOT, '_source_hunter_state.json');
const QUEUE_URL = 'http://127.0.0.1:9001';
const CYCLE_MS = 10 * 60 * 1000; // 10 minutos
const MAX_HOURS = 10;
const MAX_CYCLES = (MAX_HOURS * 60 * 60 * 1000) / CYCLE_MS;

const HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' };

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch (e) {}
  // Sem console.log — EPIPE em background shell causa crash recursivo
}

function loadState() {
  try { return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')); }
  catch (e) { return { cycle: 0, triedSites: [], integratedPlugins: [], archiveCollections: [] }; }
}

function saveState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

// ========== FASE 1: Verificar fila ==========
async function checkQueue() {
  try {
    const r = await axios.get(`${QUEUE_URL}/queue`, { timeout: 30000 });
    const q = r.data;
    const stats = {};
    q.queue.forEach(i => { stats[i.status] = (stats[i.status] || 0) + 1; });
    const pending = (stats.pending || 0) + (stats.ready || 0) + (stats.searching || 0);
    const completed = stats.completed || 0;
    const downloading = stats.downloading || 0;
    log(`Fila: ${completed} completos, ${pending} pendentes, ${downloading} baixando`);
    return { stats, pending, completed, downloading, total: q.queue.length };
  } catch (e) {
    log(`ERRO ao verificar fila: ${e.message}`);
    return null;
  }
}

// ========== FASE 2: Buscar colecoes archive.org ==========
async function searchArchiveCollections(state) {
  const queries = [
    'PSX Redump',
    'PSX Japan SLPS',
    'PlayStation CHD',
    'PSX NTSC',
    'PlayStation ROM set',
    'PSX SLPM',
    'PlayStation Redump 2024',
    'PSX bin cue',
    'PlayStation Japan iso',
    'PSX SLES'
  ];

  // Colecoes conhecidas promissoras (seed manual)
  const KNOWN_COLLECTIONS = [
    { id: 'Centuron-PSX', title: 'Centuron PSX', minFiles: 3856 },
    { id: 'sony-play-station-japan-non-redump', title: 'Sony PS Japan Non-Redump', minFiles: 599 },
    { id: '2024-sony-play-station-jap-hearto-1g1r-collection', title: '2024 PS Japan Hearto 1G1R', minFiles: 2683 }
  ];

  const found = [];

  // Primeiro processa colecoes conhecidas (seed)
  for (const kc of KNOWN_COLLECTIONS) {
    if (state.archiveCollections.includes(kc.id)) continue;
    try {
      const metaUrl = `https://archive.org/metadata/${kc.id}`;
      const meta = await axios.get(metaUrl, { headers: HEADERS, timeout: 60000 });
      if (meta.data && meta.data.files) {
        const psxFiles = meta.data.files.filter(f =>
          /\.(bin|cue|iso|chd|7z|zip)$/i.test(f.name)
        );
        const jpFiles = psxFiles.filter(f => /\(japan\)|SLPS|SCPS|SLPM/i.test(f.name));
        if (psxFiles.length > 50) {
          const isPS2 = /ps2|playstation.?2/i.test(kc.id) || /ps2|playstation.?2/i.test(kc.title || '');
          const isPSP = /psp|playstation.?portable/i.test(kc.id) || /psp|playstation.?portable/i.test(kc.title || '');
          const isPS3 = /ps3|playstation.?3/i.test(kc.id) || /ps3|playstation.?3/i.test(kc.title || '');
          if (isPS2 || isPSP || isPS3) {
            log(`Colecao conhecida ${kc.id} ignorada (PS2/PSP/PS3)`);
            state.archiveCollections.push(kc.id);
            continue;
          }
          log(`Colecao conhecida: ${kc.id} (${psxFiles.length} arquivos, ${jpFiles.length} JP)`);
          found.push({ id: kc.id, totalFiles: psxFiles.length, jpFiles: jpFiles.length, title: kc.title });
          state.archiveCollections.push(kc.id);
        }
      }
    } catch (e) {
      log(`ERRO colecao conhecida '${kc.id}': ${e.message}`);
    }
  }

  for (const q of queries) {
    if (state.triedQueries && state.triedQueries.includes(q)) continue;
    try {
      // Usa a API de busca do archive.org
      const url = `https://archive.org/advancedsearch.php?q=${encodeURIComponent(q + ' AND mediatype:software')}&fl[]=identifier&fl[]=title&rows=20&output=json`;
      const res = await axios.get(url, { headers: HEADERS, timeout: 60000 });
      if (res.data && res.data.response && res.data.response.docs) {
        for (const doc of res.data.response.docs) {
          const id = doc.identifier;
          if (state.archiveCollections.includes(id)) continue;
          if (state.triedSites.includes(id)) continue;
          // Verifica se tem arquivos PSX
          try {
            const metaUrl = `https://archive.org/metadata/${id}`;
            const meta = await axios.get(metaUrl, { headers: HEADERS, timeout: 60000 });
            if (meta.data && meta.data.files) {
              const psxFiles = meta.data.files.filter(f =>
                /\.(bin|cue|iso|chd|7z|zip)$/i.test(f.name)
              );
              const jpFiles = psxFiles.filter(f => /\(japan\)|SLPS|SCPS|SLPM/i.test(f.name));
              if (psxFiles.length > 50) {
                // Filtra PS2/PSP/PS3 - so PSX
                const isPS2 = /ps2|playstation.?2/i.test(id) || /ps2|playstation.?2/i.test(doc.title || '');
                const isPSP = /psp|playstation.?portable/i.test(id) || /psp|playstation.?portable/i.test(doc.title || '');
                const isPS3 = /ps3|playstation.?3/i.test(id) || /ps3|playstation.?3/i.test(doc.title || '');
                if (isPS2 || isPSP || isPS3) {
                  log(`Colecao ${id} ignorada (PS2/PSP/PS3)`);
                  state.archiveCollections.push(id);
                  continue;
                }
                log(`Colecao encontrada: ${id} (${psxFiles.length} arquivos, ${jpFiles.length} JP)`);
                found.push({ id, totalFiles: psxFiles.length, jpFiles: jpFiles.length, title: doc.title });
                state.archiveCollections.push(id);
              }
            }
          } catch (e) { /* skip */ }
        }
      }
      if (!state.triedQueries) state.triedQueries = [];
      state.triedQueries.push(q);
    } catch (e) {
      log(`ERRO busca archive '${q}': ${e.message}`);
    }
  }
  return found;
}

// ========== FASE 3: Criar plugin para colecao archive.org ==========
function createArchivePlugin(collection) {
  const colId = collection.id;
  const pluginName = `archive_${colId.replace(/[^a-z0-9]/gi, '_').toLowerCase()}`;
  const pluginFile = path.join(PLUGINS_DIR, `${pluginName}.js`);

  if (fs.existsSync(pluginFile)) {
    log(`Plugin ${pluginName} ja existe, pulando`);
    return null;
  }

  const code = `// Auto-gerado por _source_hunter.js para colecao archive.org: ${collection.id}
const axios = require('axios');
const { normalize, titleScore, buildSource } = require('./_base');

const HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' };
const COLLECTION = '${collection.id}';
const cache = { files: null, time: 0 };
const CACHE_TTL = 3600000;

function cleanTitle(t) {
  if (!t) return '';
  return normalize(t
    .replace(/\\(japan\\)/gi, '').replace(/\\(disc\\s*\\d+\\)/gi, '')
    .replace(/\\(en,ja,fr,de\\)/gi, '').replace(/\\(playstation the best\\)/gi, '')
    .replace(/\\(rev \\d+\\)/gi, '').replace(/\\(demo\\)/gi, '')
    .replace(/\\(beta\\)/gi, '').replace(/\\(gentei set\\)/gi, '')
    .trim());
}

async function loadFiles() {
  const now = Date.now();
  if (cache.files && now - cache.time < CACHE_TTL) return cache.files;
  try {
    const res = await axios.get(\`https://archive.org/metadata/\${COLLECTION}\`, { headers: HEADERS, timeout: 60000 });
    if (res.data && res.data.files) {
      cache.files = res.data.files
        .filter(f => /\\.(zip|7z|chd|bin|iso)$/i.test(f.name))
        .map(f => ({
          name: f.name,
          size: parseInt(f.size) || 0,
          url: \`https://archive.org/download/\${COLLECTION}/\${encodeURIComponent(f.name)}\`
        }));
      cache.time = now;
      return cache.files;
    }
  } catch (e) { /* fallback */ }
  cache.files = [];
  cache.time = now;
  return cache.files;
}

module.exports = {
  name: '${pluginName.replace(/_/g, '-')}',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 6,
  enabled: true,
  async search(serial, title) {
    if (!title) return [];
    const target = cleanTitle(title);
    if (target.length < 3) return [];
    const files = await loadFiles();
    if (!files.length) return [];
    const stopWords = new Set(['the', 'of', 'and', 'a', 'an', 'to', 'in', 'for', 'on', 'at', 'by', 'with', 'from']);
    const targetWords = target.split(' ').filter(w => w.length >= 3 && !stopWords.has(w));
    const scored = [];
    for (const f of files) {
      const fName = cleanTitle(f.name.replace(/\\.(zip|7z|chd|bin|iso)$/i, ''));
      let score = titleScore(target, fName);
      if (targetWords.length > 0) {
        const matched = targetWords.filter(w => fName.includes(w)).length;
        if (matched === targetWords.length) score = Math.max(score, 0.85);
      }
      const targetDisc = title.match(/\\(disc\\s*(\\d+)\\)/i);
      const fileDisc = f.name.match(/\\(disc\\s*(\\d+)\\)/i);
      if (targetDisc && fileDisc && targetDisc[1] !== fileDisc[1]) score *= 0.3;
      if (score >= 0.6) scored.push({ ...f, score });
    }
    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, 3).map(f =>
      buildSource('${pluginName.replace(/_/g, '-')}', f.url, title, { score: f.score, size: f.size })
    );
  }
};
`;
  fs.writeFileSync(pluginFile, code);
  log(`Plugin criado: ${pluginFile}`);
  return pluginName;
}

// ========== FASE 4: Sites ROM candidatos ==========
const CANDIDATE_SITES = [
  { name: 'freeroms', url: 'https://www.freeroms.com/psx.htm', type: 'letter' },
  { name: 'wowroms', url: 'https://www.wowroms.com/en/roms/list/playstation', type: 'letter' },
  { name: 'romsdownload', url: 'https://romsdownload.net/roms/playstation', type: 'search' },
  { name: 'portalroms', url: 'https://www.portalroms.com/en/roms/playstation', type: 'search' },
  { name: 'edgeemu', url: 'https://edgeemu.net/catalog-sony-playstation.html', type: 'search' },
  { name: 'gamulator', url: 'https://www.gamulator.com/roms/psx', type: 'search' },
  { name: 'romsmode', url: 'https://www.romsmode.com/roms/playstation', type: 'search' },
  { name: 'killerroms', url: 'https://killerroms.com/roms/sony-playstation', type: 'search' },
  { name: 'romsever', url: 'https://romsever.com/roms/playstation', type: 'search' },
  { name: 'downloadroms', url: 'https://downloadroms.org/roms/playstation', type: 'search' },
  { name: 'romsforever', url: 'https://romsforever.com/roms/playstation', type: 'search' },
  { name: 'emulatorgames', url: 'https://www.emulatorgames.net/roms/sony-playstation/', type: 'search' },
  { name: 'consoleroms', url: 'https://www.consoleroms.com/roms/playstation', type: 'search' },
  { name: 'romsplanet', url: 'https://www.romsplanet.com/roms/playstation', type: 'search' },
];

async function tryCandidateSite(site, state) {
  if (state.triedSites.includes(site.name)) return null;
  state.triedSites.push(site.name);

  try {
    const res = await axios.get(site.url, { headers: HEADERS, timeout: 15000, maxRedirects: 5 });
    if (res.status !== 200) {
      log(`Site ${site.name}: HTTP ${res.status}`);
      return null;
    }
    const html = res.data;
    // Verifica se tem ROMs PSX
    const hasPSX = /playstation|psx|ps1/i.test(html);
    const hasDownloads = /download|\.bin|\.iso|\.7z|\.zip/i.test(html);
    if (!hasPSX || !hasDownloads) {
      log(`Site ${site.name}: sem ROMs PSX detectaveis`);
      return null;
    }
    log(`Site ${site.name}: acessivel, tem ROMs PSX`);
    // Tenta extrair padrao de URL de download
    const downloadLinks = html.match(/href="([^"]*(?:rom|download|game)[^"]*)"/gi) || [];
    log(`  ${downloadLinks.length} links de download encontrados`);
    if (downloadLinks.length < 5) {
      log(`  Poucos links, pulando`);
      return null;
    }
    return { site, html, downloadLinks };
  } catch (e) {
    log(`Site ${site.name}: ERRO ${e.response ? e.response.status : e.message}`);
    return null;
  }
}

// ========== FASE 5: Integrar plugin ==========
function integratePlugin(pluginName) {
  const configPath = path.join(ROOT, 'shared', 'config.js');
  const sitesPath = path.join(ROOT, 'services', 'search', 'sites.js');
  const dlPath = path.join(ROOT, 'services', 'download', 'index.js');
  const pluginKey = pluginName.replace(/-/g, '_');
  let changed = false;

  // 1. Adiciona ao SOURCE_LIMITS em config.js
  let config = fs.readFileSync(configPath, 'utf8');
  if (!config.includes(`'${pluginKey}'`)) {
    // Insere antes do fechamento do objeto SOURCE_LIMITS
    const marker = "'archive_redump_jp': 2";
    if (config.includes(marker)) {
      config = config.replace(marker, marker + ",\n    '" + pluginKey + "': 2");
      fs.writeFileSync(configPath, config);
      log(`Adicionado ao SOURCE_LIMITS: ${pluginKey}`);
      changed = true;
    }
  }

  // 2. Adiciona ao isLocalCache e pureCacheNames em sites.js
  let sites = fs.readFileSync(sitesPath, 'utf8');
  if (!sites.includes(`'${pluginName}'`)) {
    // isLocalCache: adiciona antes do parentese final
    sites = sites.replace(
      "p.name === 'archive-redump-jp')",
      "p.name === 'archive-redump-jp' || p.name === '" + pluginName + "')"
    );
    // pureCacheNames: adiciona na lista
    sites = sites.replace(
      "'archive_redump_jp']",
      "'archive_redump_jp', '" + pluginKey + "']"
    );
    fs.writeFileSync(sitesPath, sites);
    log(`Adicionado ao sites.js: ${pluginName}`);
    changed = true;
  }

  // 3. Adiciona ao rrSources em download/index.js
  let dl = fs.readFileSync(dlPath, 'utf8');
  if (!dl.includes(`'${pluginName}'`)) {
    // Adiciona apos 'consoleroms' no array rrSources
    dl = dl.replace(
      "'consoleroms'         // RR 13",
      "'consoleroms'         // RR 13\n  '" + pluginName + "',            // RR 14 (auto)"
    );
    fs.writeFileSync(dlPath, dl);
    log(`Adicionado ao rrSources: ${pluginName}`);
    changed = true;
  }

  // 4. Adiciona ao speedMap em download/index.js
  const speedMapMarker = `'${pluginName}': 6`;
  if (!dl.includes(speedMapMarker)) {
    dl = fs.readFileSync(dlPath, 'utf8');
    if (dl.includes("'archive_redump_jp': 7,")) {
      dl = dl.replace("'archive_redump_jp': 7,", "'archive_redump_jp': 7, '" + pluginName + "': 6,");
      fs.writeFileSync(dlPath, dl);
    }
  }

  return changed;
}

// ========== FASE 6: Reiniciar servicos ==========
function restartServices() {
  try {
    // Mata search e download
    const out = execSync('powershell -Command "Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match \'services/(search|download)/index.js\' } | ForEach-Object { Stop-Process -Id $_.Id -Force }"', { timeout: 10000, encoding: 'utf8' });
    log('Servicos search+download mortos, aguardando orchestrator reiniciar...');
  } catch (e) {
    log(`Aviso ao reiniciar: ${e.message}`);
  }
}

// ========== FASE 7: Testar plugin ==========
async function testPlugin(pluginName, testSerials) {
  try {
    delete require.cache[require.resolve(path.join(PLUGINS_DIR, `${pluginName.replace(/-/g, '_')}.js`))];
    const plugin = require(path.join(PLUGINS_DIR, `${pluginName.replace(/-/g, '_')}.js`));
    if (!plugin.enabled) return false;
    let anyFound = false;
    for (const [serial, title] of testSerials) {
      try {
        const results = await Promise.race([
          plugin.search(serial, title),
          new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 30000))
        ]);
        if (results && results.length > 0) {
          log(`  TEST OK: ${serial} -> ${results.length} fontes`);
          anyFound = true;
          break;
        }
      } catch (e) {
        log(`  TEST erro: ${serial} -> ${e.message}`);
      }
    }
    return anyFound;
  } catch (e) {
    log(`  ERRO ao carregar plugin: ${e.message}`);
    return false;
  }
}

// ========== CICLO PRINCIPAL ==========
async function runCycle(state) {
  state.cycle++;
  log(`\n${'='.repeat(60)}`);
  log(`CICLO ${state.cycle}/${MAX_CYCLES}`);
  log(`${'='.repeat(60)}`);

  // 1. Verifica fila
  const queueInfo = await checkQueue();
  if (!queueInfo) {
    log('Fila indisponivel, tentando mesmo assim');
  } else if (queueInfo.pending === 0 && queueInfo.downloading === 0) {
    log('TODOS DOWNLOADS COMPLETOS! Encerrando...');
    return true; // done
  }

  // 2. Busca novas colecoes archive.org
  log('\n--- Buscando colecoes archive.org ---');
  const collections = await searchArchiveCollections(state);
  let newPlugins = 0;

  for (const col of collections) {
    const pluginName = createArchivePlugin(col);
    if (!pluginName) continue;

    // Testa o plugin
    const testSerials = [
      ['SLPS-01348', 'G-Darius (Japan)'],
      ['SLUS-00426', 'MDK (USA)'],
      ['SLES-00567', 'Crash Bandicoot (Europe)'],
      ['SLPM-87286', 'GeGeGe no Kitarou (Japan)'],
      ['SCPS-10015', 'Battle Arena Toshinden (Japan)']
    ];

    log(`Testando plugin ${pluginName}...`);
    const ok = await testPlugin(pluginName, testSerials);
    if (ok) {
      log(`Integrando ${pluginName}...`);
      const integrated = integratePlugin(pluginName.replace(/_/g, '-'));
      if (integrated) {
        state.integratedPlugins.push(pluginName);
        newPlugins++;
      }
    } else {
      log(`Plugin ${pluginName} nao passou no teste, desativando`);
      // Desativa plugin nao funcional
      const pFile = path.join(PLUGINS_DIR, `${pluginName.replace(/-/g, '_')}.js`);
      let content = fs.readFileSync(pFile, 'utf8');
      content = content.replace(/enabled:\s*true/, 'enabled: false');
      fs.writeFileSync(pFile, content);
    }
  }

  // 3. Tenta sites candidatos
  log('\n--- Testando sites ROM candidatos ---');
  for (const site of CANDIDATE_SITES) {
    if (state.triedSites.includes(site.name)) continue;
    const result = await tryCandidateSite(site, state);
    if (result) {
      log(`Site ${site.name} promissor, mas plugin manual necessario`);
      // Sites nao-archive precisam de plugin manual (HTML scraping complexo)
      // Apenas loga para analise futura
    }
  }

  // 4. Reinicia servicos se novos plugins foram integrados
  if (newPlugins > 0) {
    log(`\n${newPlugins} novos plugins integrados, reiniciando servicos...`);
    restartServices();
  } else {
    log('\nNenhum plugin novo neste ciclo');
  }

  // 5. Salva estado
  saveState(state);
  log(`Estado salvo. Proximo ciclo em 10 minutos.`);

  return false; // not done
}

// ========== MAIN ==========
async function main() {
  log('='.repeat(60));
  log('SOURCE HUNTER INICIADO');
  log(`Duracao: ${MAX_HOURS}h | Ciclos: ${MAX_CYCLES} | Intervalo: 10min`);
  log('='.repeat(60));

  let state = loadState();
  log(`Estado carregado: ciclo ${state.cycle}, ${state.integratedPlugins.length} plugins integrados`);

  for (let i = state.cycle; i < MAX_CYCLES; i++) {
    try {
      const done = await runCycle(state);
      if (done) {
        log('Todos downloads completos! Encerrando source hunter.');
        break;
      }
    } catch (e) {
      log(`ERRO no ciclo ${state.cycle}: ${e.message}`);
      log(e.stack || '');
    }

    if (state.cycle >= MAX_CYCLES) {
      log('Limite de ciclos atingido. Encerrando.');
      break;
    }

    // Aguarda 10 minutos
    log(`Aguardando 10 minutos para proximo ciclo...`);
    await new Promise(r => setTimeout(r, CYCLE_MS));
  }

  log('SOURCE HUNTER FINALIZADO');
}

// Graceful shutdown
process.on('SIGINT', () => {
  log('SIGINT recebido, salvando estado e saindo...');
  const state = loadState();
  saveState(state);
  process.exit(0);
});

process.on('SIGTERM', () => {
  log('SIGTERM recebido, salvando estado e saindo...');
  const state = loadState();
  saveState(state);
  process.exit(0);
});

process.on('unhandledRejection', (reason, promise) => {
  log(`UNHANDLED REJECTION: ${reason}`);
});

process.on('uncaughtException', (err) => {
  if (err && (err.code === 'EPIPE' || err.code === 'ERR_STREAM_DESTROYED')) return; // ignora silenciosamente
  try { log(`UNCAUGHT EXCEPTION: ${err.message}`); } catch (e) {}
  try { log(err.stack || ''); } catch (e) {}
  try {
    const state = loadState();
    saveState(state);
  } catch (e) {}
});

main().catch(e => {
  log(`ERRO FATAL: ${e.message}`);
  log(e.stack || '');
  process.exit(1);
});
