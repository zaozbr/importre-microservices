// Reindexa seriais JP faltantes buscando por titulo no archive.org via Tor (HTTPS)
// Roda uma vez e salva os resultados em archive_jp_dynamic.json
const axios = require('axios');
const fs = require('fs');
const path = require('path');

const STATE_DIR = 'F:\\importre_state';
const QUEUE_PATH = path.join(STATE_DIR, 'queue.json');
const JP_INDEX_PATH = path.join(STATE_DIR, 'archive_jp_index.json');
const DYNAMIC_INDEX_PATH = path.join(STATE_DIR, 'archive_jp_dynamic.json');

function cleanTitleStr(title) {
  return title.replace(/\[.*?\]|\(.*?\)/g, '').trim().replace(/\s+/g, ' ');
}

async function searchArchiveOrg(cleanTitle, serial, hdrs, getProxy) {
  // Buscar por titulo - filtrar para PSX apenas (excluir PC, PS2, etc)
  const q = encodeURIComponent(`(${cleanTitle}) AND (collection:psx OR collection:redump OR collection:sony_playstation OR collection:psx-chd-roms OR collection:softwarelibrary_psx) NOT collection:*pc* NOT collection:*ps2*`);
  // Tentar HTTPS via Tor primeiro, fallback para HTTP
  const urlHttps = `https://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=downloads&rows=5&output=json`;
  const urlHttp = `http://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=downloads&rows=5&output=json`;
  let res;
  try {
    res = await axios.get(urlHttps, { timeout: 45000, headers: hdrs, ...getProxy(urlHttps) });
  } catch {
    // Fallback HTTP (porta 80, nao passa por Tor)
    res = await axios.get(urlHttp, { timeout: 60000, headers: hdrs });
  }
  const docs = res.data?.response?.docs || [];
  if (!docs.length) return null;
  // Filtrar resultados que parecem PC/PS2
  const psxDocs = docs.filter(d => {
    const id = (d.identifier || '').toLowerCase();
    return !id.includes('pc') && !id.includes('ps2') && !id.includes('playstation2');
  });
  if (!psxDocs.length) return null;
  const metaUrl = `https://archive.org/metadata/${psxDocs[0].identifier}`;
  const metaUrlHttp = `http://archive.org/metadata/${psxDocs[0].identifier}`;
  let meta;
  try {
    meta = await axios.get(metaUrl, { timeout: 30000, headers: hdrs, ...getProxy(metaUrl) });
  } catch {
    meta = await axios.get(metaUrlHttp, { timeout: 30000, headers: hdrs });
  }
  const files = meta.data?.files || [];
  const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso|chd)$/i.test(f.name) && f.size > 1024 * 1024);
  if (!romFiles.length) return null;
  const best = romFiles.find(f => f.name.toLowerCase().includes(serial.toLowerCase())) || romFiles[0];
  return { collection: psxDocs[0].identifier, file: best.name, size: parseInt(best.size) || 0, title: psxDocs[0].title, dynamic: true };
}

async function main() {
  const { getArchiveHeaders } = require('../shared/archive_auth');
  const { getAxiosProxyConfig } = require('../shared/tor_proxy');
  const hdrs = getArchiveHeaders();

  const q = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf8'));
  const pending = q.queue.filter(i => i.status === 'pending' && i.title);
  const jpIdx = JSON.parse(fs.readFileSync(JP_INDEX_PATH, 'utf8'));
  const missing = pending.filter(i => !jpIdx[i.serial]);
  console.log(`Seriais pending sem indice JP: ${missing.length}`);

  const dynamic = {};
  let found = 0;

  for (const item of missing) {
    const { serial, title } = item;
    if (!title || title.length < 3) continue;
    const cleanTitle = cleanTitleStr(title);
    if (cleanTitle.length < 3) continue;

    try {
      const result = await searchArchiveOrg(cleanTitle, serial, hdrs, getAxiosProxyConfig);
      if (result) {
        dynamic[serial] = result;
        found++;
        console.log(`[OK] ${serial} -> ${result.collection}/${result.file}`);
      } else {
        console.log(`[MISS] ${serial} -> "${cleanTitle}" nao encontrado`);
      }
    } catch (e) {
      if (e.response?.status === 429) {
        console.log(`[429] ${serial}: rate limit. Aguardando 10s...`);
        await new Promise(r => setTimeout(r, 10000));
        try {
          const result = await searchArchiveOrg(cleanTitle, serial, hdrs, getAxiosProxyConfig);
          if (result) {
            dynamic[serial] = result;
            found++;
            console.log(`[OK-RETRY] ${serial} -> ${result.collection}/${result.file}`);
          }
        } catch (e2) {
          console.log(`[ERR-RETRY] ${serial}: ${e2.message}`);
        }
      } else {
        console.log(`[ERR] ${serial}: ${e.message}`);
      }
    }
    await new Promise(r => setTimeout(r, 3000));
  }

  fs.writeFileSync(DYNAMIC_INDEX_PATH, JSON.stringify(dynamic, null, 2));
  console.log(`\nIndice dinamico salvo: ${found} seriais encontrados de ${missing.length} pendentes`);
  console.log(`Arquivo: ${DYNAMIC_INDEX_PATH}`);
}

main().catch(e => console.error('Erro:', e));
