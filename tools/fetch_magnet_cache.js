/**
 * fetch_magnet_cache.js
 *
 * Busca magnet links de todas as colecoes archive.org conhecidas
 * e salva em _magnet_cache.json para uso pelos plugins de search.
 *
 * Uso: node tools/fetch_magnet_cache.js
 */
const axios = require('axios');
const fs = require('fs');
const path = require('path');

const COLLECTIONS = [
  '2024-sony-playstation-usa-hearto-1g1r-collection',
  'Centuron-PSX',
  'chd_psx_jap',
  'gamelist_202205',
  'PS1_EU_CHD_Arquivista',
  'PSXImageFiles',
  'RedumpSonyPlayStationAmerica20160617',
  'slpm-87056-winning-eleven-2002-rips',
  'sony-play-station-japan-non-redump',
  'sony_playstation_part1',
  'we2002-estadios-3d',
  // Colecoes adicionais para buscar seriais faltantes
  'redumpSonyPlayStationJapan',
  'SonyPlaystationJapan',
  'psx-roms-archive',
  'PSXCHD',
  'PlayStationCHD',
];

const HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' };

// Adicionar cookie do archive.org se disponivel
try {
  const cookieFile = path.join(__dirname, '..', 'archive_cookies.txt');
  if (fs.existsSync(cookieFile)) {
    const content = fs.readFileSync(cookieFile, 'utf8');
    const sigMatch = content.match(/logged-in-sig\t(\S+)/);
    const userMatch = content.match(/logged-in-user\t(\S+)/);
    if (sigMatch && userMatch) {
      HEADERS.Cookie = `logged-in-sig=${sigMatch[1]}; logged-in-user=${userMatch[1]}`;
    }
  }
} catch {}
const OUT_FILE = path.join(__dirname, '..', '_magnet_cache.json');

async function fetchCollectionMeta(id) {
  try {
    const res = await axios.get(`https://archive.org/metadata/${id}`, { headers: HEADERS, timeout: 30000 });
    if (!res.data) return null;

    const data = res.data;
    const files = data.files || [];

    // Procurar arquivo .torrent nos metadados
    const torrentFile = files.find(f => f.name && f.name.endsWith('.torrent'));
    let magnet = null;
    let infoHash = null;

    if (torrentFile) {
      // Archive.org gera torrent automaticamente — construir magnet
      const torrentUrl = `https://archive.org/download/${id}/${torrentFile.name}`;
      try {
        const torRes = await axios.get(torrentUrl, { headers: HEADERS, timeout: 30000, responseType: 'arraybuffer' });
        const torrentBuf = Buffer.from(torRes.data);
        // Extrair info_hash do torrent (bencode)
        infoHash = extractInfoHash(torrentBuf);
        if (infoHash) {
          magnet = `magnet:?xt=urn:btih:${infoHash}&dn=${encodeURIComponent(data.metadata?.title || id)}`;
          // Adicionar trackers do archive.org
          magnet += '&tr=https://tracker.archive.org/announce';
          magnet += '&tr=udp://tracker.archive.org:6969/announce';
          magnet += '&tr=wss://tracker.archive.org/';
        }
      } catch (e) {
        console.log(`  Erro baixando torrent de ${id}: ${e.message}`);
      }
    }

    // Se nao tem torrent, usar magnet direto do archive.org
    if (!magnet) {
      // Archive.org tem endpoint de magnet
      try {
        const magRes = await axios.get(`https://archive.org/metadata/${id}`, { headers: HEADERS, timeout: 10000 });
        if (magRes.data?.server) {
          // Construir magnet via info_hash do archive.org
          const ih = data.metadata?.identifier?.replace(/-/g, '').substring(0, 40);
          if (ih && ih.length === 40) {
            magnet = `magnet:?xt=urn:btih:${ih}&dn=${encodeURIComponent(data.metadata?.title || id)}`;
            magnet += '&tr=https://tracker.archive.org/announce';
            magnet += '&tr=udp://tracker.archive.org:6969/announce';
            infoHash = ih;
          }
        }
      } catch {}
    }

    // Listar arquivos ROM do torrent
    const romFiles = files
      .filter(f => /\.(zip|7z|chd|bin|iso|cue|img)$/i.test(f.name) && parseInt(f.size || 0) > 1024 * 1024)
      .map((f, i) => ({ path: f.name, size: parseInt(f.size || 0), index: i + 1 }));

    return {
      magnet,
      infoHash,
      files: romFiles,
      title: data.metadata?.title || id,
      fileCount: romFiles.length,
    };
  } catch (e) {
    console.log(`  Erro metadata ${id}: ${e.message}`);
    return null;
  }
}

function extractInfoHash(torrentBuf) {
  // Parser bencode simples para extrair info_hash
  // O info_hash e o hash SHA1 do conteudo da chave "info" no torrent
  try {
    const str = torrentBuf.toString('latin1');
    const infoIdx = str.indexOf('4:infod');
    if (infoIdx === -1) return null;
    // O dicionario info comeca apos "4:info"
    const infoStart = infoIdx + 6;
    // Encontrar o fim do dicionario info (ultimo 'e' antes do fim)
    let depth = 1;
    let i = infoStart + 1;
    while (i < str.length && depth > 0) {
      if (str[i] === 'd' || str[i] === 'l') depth++;
      else if (str[i] === 'e') depth--;
      i++;
    }
    const infoContent = torrentBuf.slice(infoStart, i);
    const crypto = require('crypto');
    return crypto.createHash('sha1').update(infoContent).digest('hex');
  } catch {
    return null;
  }
}

(async () => {
  console.log('=== Buscando magnet links de colecoes archive.org ===');
  const cache = {};
  for (const id of COLLECTIONS) {
    console.log(`Buscando ${id}...`);
    const data = await fetchCollectionMeta(id);
    if (data) {
      cache[id] = data;
      console.log(`  OK: ${data.fileCount} arquivos, magnet=${data.magnet ? 'sim' : 'nao'}`);
    } else {
      console.log(`  FALHOU`);
    }
  }

  fs.writeFileSync(OUT_FILE, JSON.stringify(cache, null, 2));
  console.log(`\nSalvo em ${OUT_FILE}`);
  console.log(`Colecoes com magnet: ${Object.values(cache).filter(c => c.magnet).length}/${Object.keys(cache).length}`);
})();
