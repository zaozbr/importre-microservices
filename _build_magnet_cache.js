/**
 * _build_magnet_cache.js
 *
 * Baixa os .torrents das colecoes archive.org, extrai info-hashes
 * e gera magnet links para cache local.
 *
 * Uso: node _build_magnet_cache.js
 *
 * Saida: _magnet_cache.json
 *   {
 *     "Centuron-PSX": { "magnet": "magnet:?...", "infoHash": "abc...", "files": [...] },
 *     ...
 *   }
 *
 * Os magnet links usam trackers do archive.org + DHT, entao funcionam
 * mesmo se archive.org sair do ar (DHT resolve peers).
 */
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ARIA2C = path.join(__dirname, 'aria2c.exe');
const CACHE_FILE = path.join(__dirname, '_magnet_cache.json');
const TORRENT_DIR = path.join(__dirname, '_torrents');

// Trackers do archive.org + publicos para robustez
const TRACKERS = [
  'udp://tracker.archive.org:6969/announce',
  'http://tracker.archive.org:6969/announce',
  'udp://tracker.opentrackr.org:1337/announce',
  'udp://open.demonii.com:1337/announce',
  'udp://tracker.torrent.eu.org:451/announce',
  'udp://exodus.desync.com:6969/announce',
  'udp://tracker.tiny-vps.com:6969/announce'
];

// Colecoes ativas (devem bater com os plugins archive_*)
const COLLECTIONS = [
  { id: 'Centuron-PSX', plugin: 'archive-centuron-psx' },
  { id: 'chd_psx_jap', plugin: 'archive_chd_jp' },
  { id: 'gamelist_202205', plugin: 'archive-gamelist-202205' },
  { id: 'PS1_EU_CHD_Arquivista', plugin: 'archive-ps1-eu-chd-arquivista' },
  { id: 'PSXImageFiles', plugin: 'archive-psximagefiles' },
  { id: 'RedumpSonyPlayStationAmerica20160617', plugin: 'archive-redumpsonyplaystationamerica20160617' },
  { id: 'sony_playstation_part1', plugin: 'archive-sony-playstation-part1' },
  { id: 'sony-play-station-japan-non-redump', plugin: 'archive-sony-play-station-japan-non-redump' }
];

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

/**
 * Baixa o .torrent de uma colecao via aria2c.
 */
function downloadTorrentFile(collectionId) {
  return new Promise((resolve, reject) => {
    const torrentUrl = `https://archive.org/download/${collectionId}/${collectionId}_archive.torrent`;
    const outFile = path.join(TORRENT_DIR, `${collectionId}.torrent`);
    const args = [
      torrentUrl,
      `--dir=${TORRENT_DIR}`,
      `--out=${collectionId}.torrent`,
      '--max-connection-per-server=16',
      '--split=16',
      '--max-tries=3',
      '--retry-wait=5',
      '--timeout=60',
      '--connect-timeout=30',
      '--continue=true',
      '--file-allocation=none',
      '--console-log-level=warn'
    ];
    const proc = spawn(ARIA2C, args, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = '';
    proc.stderr.on('data', d => { stderr += d.toString(); });
    proc.on('exit', (code) => {
      if (code === 0 && fs.existsSync(outFile)) resolve(outFile);
      else reject(new Error(`aria2c exit ${code}: ${stderr.slice(0, 200)}`));
    });
  });
}

/**
 * Extrai info-hash de um arquivo .torrent usando aria2c --show-files.
 * O info-hash aparece na saida como "Info Hash: <hex>".
 */
function extractInfoHash(torrentPath) {
  return new Promise((resolve, reject) => {
    const args = ['--show-files=true', '--bt-metadata-only=true', torrentPath];
    const proc = spawn(ARIA2C, args, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '';
    proc.stdout.on('data', d => { output += d.toString(); });
    proc.stderr.on('data', d => { output += d.toString(); });
    proc.on('exit', () => {
      // Procurar por "Info Hash:" ou "infoHash:"
      const hashMatch = output.match(/Info\s*Hash[:\s]+([a-fA-F0-9]{40})/i);
      if (hashMatch) {
        resolve(hashMatch[1].toLowerCase());
      } else {
        // Tentar outro formato
        const hashMatch2 = output.match(/([a-fA-F0-9]{40})/);
        if (hashMatch2) resolve(hashMatch2[1].toLowerCase());
        else reject(new Error('info-hash nao encontrado na saida'));
      }
    });
  });
}

/**
 * Extrai lista de arquivos do torrent.
 */
function extractFileList(torrentPath) {
  return new Promise((resolve) => {
    const args = ['--show-files=true', '--bt-metadata-only=true', torrentPath];
    const proc = spawn(ARIA2C, args, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '';
    proc.stdout.on('data', d => { output += d.toString(); });
    proc.stderr.on('data', d => { output += d.toString(); });
    proc.on('exit', () => {
      const files = [];
      // Formato: idx|path/to/file|size
      const lines = output.split('\n');
      for (const line of lines) {
        const m = line.match(/^\s*(\d+)\|(.+?)\|(\d+)/);
        if (m) {
          files.push({ index: parseInt(m[1]), path: m[2].trim(), size: parseInt(m[3]) });
        }
      }
      resolve(files);
    });
  });
}

/**
 * Gera magnet link a partir de info-hash, nome e trackers.
 */
function buildMagnet(infoHash, name) {
  const dn = encodeURIComponent(name);
  const tr = TRACKERS.map(t => `&tr=${encodeURIComponent(t)}`).join('');
  return `magnet:?xt=urn:btih:${infoHash}&dn=${dn}${tr}`;
}

async function main() {
  console.log('=== BUILD MAGNET CACHE ===');
  console.log(`Colecoes: ${COLLECTIONS.length}`);
  console.log('');

  // Criar diretorio de torrents
  if (!fs.existsSync(TORRENT_DIR)) fs.mkdirSync(TORRENT_DIR, { recursive: true });

  // Carregar cache existente
  let cache = {};
  if (fs.existsSync(CACHE_FILE)) {
    try { cache = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8')); } catch { cache = {}; }
  }

  for (const col of COLLECTIONS) {
    console.log(`[${col.plugin}] Processando ${col.id}...`);

    // Pular se ja temos no cache e o .torrent existe
    if (cache[col.id] && cache[col.id].magnet) {
      console.log(`  Ja cacheado: ${cache[col.id].infoHash}`);
      continue;
    }

    const torrentPath = path.join(TORRENT_DIR, `${col.id}.torrent`);

    // Baixar .torrent se nao existir
    if (!fs.existsSync(torrentPath)) {
      try {
        console.log(`  Baixando .torrent...`);
        await downloadTorrentFile(col.id);
        console.log(`  .torrent baixado: ${fs.statSync(torrentPath).size} bytes`);
      } catch (e) {
        console.log(`  ERRO baixando .torrent: ${e.message}`);
        continue;
      }
    } else {
      console.log(`  .torrent ja existe localmente`);
    }

    // Extrair info-hash
    try {
      console.log(`  Extraindo info-hash...`);
      const infoHash = await extractInfoHash(torrentPath);
      console.log(`  Info-hash: ${infoHash}`);

      // Extrair lista de arquivos
      const files = await extractFileList(torrentPath);
      console.log(`  Arquivos no torrent: ${files.length}`);

      // Gerar magnet link
      const magnet = buildMagnet(infoHash, col.id);
      console.log(`  Magnet: ${magnet.substring(0, 100)}...`);

      // Salvar no cache
      cache[col.id] = {
        magnet,
        infoHash,
        plugin: col.plugin,
        files: files.map(f => ({ index: f.index, path: f.path, size: f.size }))
      };
    } catch (e) {
      console.log(`  ERRO extraindo info-hash: ${e.message}`);
    }

    // Pausa entre colecoes para nao saturar archive.org
    await sleep(2000);
  }

  // Salvar cache
  fs.writeFileSync(CACHE_FILE, JSON.stringify(cache, null, 2));
  console.log('');
  console.log(`=== CACHE SALVO: ${CACHE_FILE} ===`);
  console.log(`Colecoes cacheadas: ${Object.keys(cache).length}`);
  for (const [id, data] of Object.entries(cache)) {
    console.log(`  ${id}: ${data.infoHash} (${data.files?.length || 0} arquivos)`);
  }
}

main().catch(e => console.log('Erro fatal:', e.message));
