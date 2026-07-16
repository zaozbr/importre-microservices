// Reindexa seriais JP faltantes buscando por titulo no archive.org via Tor (HTTPS)
// Roda uma vez e salva os resultados em archive_jp_dynamic.json
const axios = require('axios');
const fs = require('fs');
const path = require('path');

const STATE_DIR = 'F:\\importre_state';
const QUEUE_PATH = path.join(STATE_DIR, 'queue.json');
const JP_INDEX_PATH = path.join(STATE_DIR, 'archive_jp_index.json');
const DYNAMIC_INDEX_PATH = path.join(STATE_DIR, 'archive_jp_dynamic.json');

async function main() {
  const { getArchiveHeaders } = require('../shared/archive_auth');
  const { getAxiosProxyConfig } = require('../shared/tor_proxy');
  const hdrs = getArchiveHeaders();

  // Ler queue
  const q = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf8'));
  const pending = q.queue.filter(i => i.status === 'pending' && i.title);

  // Ler indice JP existente
  const jpIdx = JSON.parse(fs.readFileSync(JP_INDEX_PATH, 'utf8'));

  // Filtrar seriais que nao estao no indice
  const missing = pending.filter(i => !jpIdx[i.serial]);
  console.log(`Seriais pending sem indice JP: ${missing.length}`);

  const dynamic = {};
  let found = 0;

  for (const item of missing) {
    const { serial, title } = item;
    if (!title || title.length < 3) continue;

    try {
      // Buscar por titulo no archive.org via Tor (HTTPS - mais rapido que HTTP)
      const cleanTitle = title.replace(/\[.*?\]|\(.*?\)/g, '').trim().replace(/\s+/g, ' ');
      if (cleanTitle.length < 3) continue;

      const q = encodeURIComponent(`(${cleanTitle}) AND (collection:psx OR collection:redump OR collection:sony_playstation)`);
      const url = `https://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=downloads&rows=5&output=json`;
      const res = await axios.get(url, { timeout: 90000, headers: hdrs, ...getAxiosProxyConfig(url) });
      const docs = res.data?.response?.docs || [];

      if (docs.length > 0) {
        // Pegar metadata do primeiro resultado
        const metaUrl = `https://archive.org/metadata/${docs[0].identifier}`;
        const meta = await axios.get(metaUrl, { timeout: 30000, headers: hdrs, ...getAxiosProxyConfig(metaUrl) });
        const files = meta.data?.files || [];
        const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso|chd)$/i.test(f.name) && f.size > 1024 * 1024);

        if (romFiles.length > 0) {
          const best = romFiles.find(f => f.name.toLowerCase().includes(serial.toLowerCase())) || romFiles[0];
          dynamic[serial] = {
            collection: docs[0].identifier,
            file: best.name,
            size: parseInt(best.size) || 0,
            title: docs[0].title,
            dynamic: true
          };
          found++;
          console.log(`[OK] ${serial} -> ${docs[0].identifier}/${best.name}`);
        } else {
          console.log(`[SKIP] ${serial} -> ${docs[0].identifier} (sem ROMs)`);
        }
      } else {
        console.log(`[MISS] ${serial} -> "${cleanTitle}" nao encontrado`);
      }
    } catch (e) {
      console.log(`[ERR] ${serial}: ${e.message}`);
    }
    // Pequeno delay para nao sobrecarregar o Tor
    await new Promise(r => setTimeout(r, 1000));
  }

  // Salvar indice dinamico
  fs.writeFileSync(DYNAMIC_INDEX_PATH, JSON.stringify(dynamic, null, 2));
  console.log(`\nIndice dinamico salvo: ${found} seriais encontrados de ${missing.length} pendentes`);
  console.log(`Arquivo: ${DYNAMIC_INDEX_PATH}`);
}

main().catch(e => console.error('Erro:', e));
