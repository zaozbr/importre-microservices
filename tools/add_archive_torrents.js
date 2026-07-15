/**
 * add_archive_torrents.js
 *
 * Adiciona torrents do archive.org no aria2 (processo unico, porta 16810).
 * Para cada torrent:
 *   1. Baixa .torrent da colecao
 *   2. Adiciona no aria2 via RPC (aria2.addTorrent)
 *   3. Imediatamente usa aria2.changeOption com select-file para baixar
 *      APENAS arquivos que ainda nao temos em D:\roms\library\roms\psx
 *
 * Uso: node tools/add_archive_torrents.js
 */
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const http = require('http');

const ROM_DIR = 'D:\\roms\\library\\roms\\psx';
const COOKIE_FILE = path.join(__dirname, '..', 'archive_cookies.txt');
const ARIA2_PORT = 16810;

const COLLECTIONS = [
  'Centuron-PSX',
  'RedumpSonyPlayStationAmerica20160617',
  'sony_playstation_part1',
  'PSXImageFiles',
  'sony-play-station-japan-non-redump',
  '2024-sony-playstation-usa-hearto-1g1r-collection',
  'psx-roms-archive',
  'slpm-87056-winning-eleven-2002-rips',
];

function getHeaders() {
  const h = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' };
  try {
    const c = fs.readFileSync(COOKIE_FILE, 'utf8');
    const sig = c.match(/logged-in-sig\t(\S+)/);
    const user = c.match(/logged-in-user\t(\S+)/);
    if (sig && user) h.Cookie = `logged-in-sig=${sig[1]}; logged-in-user=${user[1]}`;
  } catch {}
  return h;
}

function aria2Rpc(method, params) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({ jsonrpc: '2.0', method, id: '1', params });
    const req = http.request(
      { hostname: '127.0.0.1', port: ARIA2_PORT, path: '/jsonrpc', method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } },
      res => { let b = ''; res.on('data', d => { b += d; }); res.on('end', () => { try { return resolve(JSON.parse(b)); } catch (e) { reject(e); } }); }
    );
    req.on('error', reject);
    req.setTimeout(120000, () => { req.destroy(); reject(new Error('timeout')); });
    req.write(data); req.end();
  });
}

// Extrai seriais do nome dos .chd existentes
function getExistingSerials() {
  const files = fs.readdirSync(ROM_DIR).filter(f => f.endsWith('.chd'));
  const serials = new Set();
  for (const f of files) {
    const m = f.match(/((?:SLES|SLUS|SLPS|SLPM|SCES|SCUS|SCPS|SLED|SCED|PBPX|SLKA|HBREW|HEXB)[-_]?\d+)/i);
    if (m) serials.add(m[1].toUpperCase().replace(/_/g, '-'));
  }
  return serials;
}

// Nomes base dos .chd existentes (sem extensao)
function getExistingBaseNames() {
  const files = fs.readdirSync(ROM_DIR).filter(f => f.endsWith('.chd'));
  return new Set(files.map(f => f.toLowerCase().replace(/\.chd$/, '')));
}

// Verifica se um arquivo do torrent ja existe na nossa colecao
function fileAlreadyExists(fileName, existingSerials, existingBaseNames) {
  const lower = fileName.toLowerCase();
  const baseName = lower.replace(/\.(zip|7z|chd|bin|iso|cue|img|rar)$/i, '');
  // Match por nome base
  if (existingBaseNames.has(baseName)) return true;
  // Match por serial
  const m = fileName.match(/((?:SLES|SLUS|SLPS|SLPM|SCES|SCUS|SCPS|SLED|SCED|PBPX|SLKA|HBREW|HEXB)[-_]?\d+)/i);
  if (m) {
    const serial = m[1].toUpperCase().replace(/_/g, '-');
    if (existingSerials.has(serial)) return true;
  }
  return false;
}

// Obter lista de arquivos da colecao via metadata API
async function getCollectionFiles(collectionId) {
  const headers = getHeaders();
  const res = await axios.get(`https://archive.org/metadata/${collectionId}`, { headers, timeout: 30000 });
  const files = res.data?.files || [];
  // O torrent lista arquivos em ordem — os indices do select-file sao 1-based
  // na ordem que aparecem no torrent. A metadata API pode ter ordem diferente.
  // Precisamos filtrar apenas ROMs e manter a ordem original do torrent.
  return files
    .map((f, i) => ({ name: f.name, size: parseInt(f.size || 0), index: i + 1 }))
    .filter(f => /\.(zip|7z|chd|bin|iso|cue|img|rar)$/i.test(f.name) && f.size > 1024 * 1024);
}

async function processCollection(collectionId, existingSerials, existingBaseNames) {
  console.log(`\n=== ${collectionId} ===`);

  // 1. Listar arquivos da colecao
  let files;
  try {
    files = await getCollectionFiles(collectionId);
  } catch (e) {
    console.log(`  ERRO metadata: ${e.message}`);
    return;
  }
  console.log(`  Arquivos ROM: ${files.length}`);

  // 2. Determinar quais faltam
  const needed = files.filter(f => !fileAlreadyExists(f.name, existingSerials, existingBaseNames));
  const alreadyHave = files.length - needed.length;
  console.log(`  Ja temos: ${alreadyHave} | Faltando: ${needed.length}`);

  if (needed.length === 0) {
    console.log(`  Pulando — todos arquivos ja existem`);
    return;
  }

  // 3. Baixar .torrent
  const torrentUrl = `https://archive.org/download/${collectionId}/${collectionId}_archive.torrent`;
  const headers = getHeaders();
  let torrentBuf;
  try {
    const res = await axios.get(torrentUrl, { headers, timeout: 120000, responseType: 'arraybuffer' });
    torrentBuf = Buffer.from(res.data);
    console.log(`  Torrent: ${(torrentBuf.length / 1024).toFixed(0)}KB`);
  } catch (e) {
    console.log(`  ERRO baixando torrent: ${e.message}`);
    return;
  }

  // 4. Adicionar no aria2 (sem select-file inicialmente)
  const torrentB64 = torrentBuf.toString('base64');
  const destDir = `F:\\downloads\\torrents\\${collectionId}`;
  if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });

  const addOpts = {
    dir: destDir,
    'seed-time': '0',
    'seed-ratio': '0',
    'max-upload-limit': '256K',
    'bt-max-peers': '100',
  };

  let gid;
  try {
    const result = await aria2Rpc('aria2.addTorrent', [torrentB64, [], addOpts]);
    if (result.error) {
      console.log(`  ERRO addTorrent: ${result.error.message}`);
      return;
    }
    gid = result.result;
    console.log(`  Torrent adicionado! GID: ${gid}`);
  } catch (e) {
    console.log(`  ERRO addTorrent: ${e.message}`);
    return;
  }

  // 5. Aplicar select-file com apenas os arquivos que faltam
  //    Se faltam todos, nao precisa de select-file
  if (alreadyHave > 0 && needed.length < files.length) {
    const selectIndices = needed.map(f => f.index).join(',');
    try {
      const changeResult = await aria2Rpc('aria2.changeOption', [gid, { 'select-file': selectIndices }]);
      if (changeResult.error) {
        console.log(`  ERRO changeOption: ${changeResult.error.message}`);
      } else {
        console.log(`  select-file aplicado: ${needed.length} arquivos selecionados (removidos ${alreadyHave})`);
      }
    } catch (e) {
      console.log(`  ERRO changeOption: ${e.message}`);
    }
  } else {
    console.log(`  Baixando todos os ${needed.length} arquivos (select-file nao necessario)`);
  }

  // 6. Status do torrent
  try {
    const status = await aria2Rpc('aria2.tellStatus', [gid, ['gid', 'downloadSpeed', 'totalLength', 'completedLength', 'bittorrent']]);
    const s = status.result || {};
    const spd = parseInt(s.downloadSpeed || 0);
    const total = parseInt(s.totalLength || 0);
    const done = parseInt(s.completedLength || 0);
    const bt = s.bittorrent ? `peers=${s.bittorrent.numPeers || 0}` : 'n/a';
    console.log(`  Status: ${(spd / 1048576).toFixed(1)}MB/s | ${((done / total) * 100).toFixed(1)}% | ${bt}`);
  } catch {}
}

(async () => {
  console.log('=== Add Archive Torrents (select-file) ===');

  const existingSerials = getExistingSerials();
  const existingBaseNames = getExistingBaseNames();
  console.log(`CHDs existentes: ${existingBaseNames.size} (${existingSerials.size} seriais unicos)`);

  // Verificar aria2
  try {
    const ver = await aria2Rpc('aria2.getVersion', []);
    if (ver.error) throw new Error(ver.error.message);
    console.log(`aria2 conectado na porta ${ARIA2_PORT} v${ver.result.version}`);
  } catch (e) {
    console.log(`ERRO: aria2 nao responde: ${e.message}`);
    process.exit(1);
  }

  for (const col of COLLECTIONS) {
    await processCollection(col, existingSerials, existingBaseNames);
  }

  // Status final
  try {
    const active = await aria2Rpc('aria2.tellActive', []);
    const a = active.result || [];
    let bt = 0, http = 0, spd = 0;
    a.forEach(i => { spd += parseInt(i.downloadSpeed || 0); if (i.bittorrent) bt++; else http++; });
    console.log(`\n=== Resultado ===`);
    console.log(`Downloads ativos: ${a.length} (BT: ${bt}, HTTP: ${http}) | ${(spd / 1048576).toFixed(1)}MB/s`);
  } catch {}
})();
