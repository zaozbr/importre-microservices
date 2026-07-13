// Expande indice do archive.org buscando seriais pendentes via API
// Uso: node tools/expand_archive_index.js
const fs = require('fs');
const axios = require('axios');
const path = require('path');
const { STATE_DIR, QUEUE_PATH } = require('../shared/config');

const ARCHIVE_NAME_INDEX = path.join(STATE_DIR, 'archive_name_index.json');
const ARCHIVE_JP_INDEX = path.join(STATE_DIR, 'archive_jp_index.json');

async function main() {
  const q = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
  const pending = q.queue.filter(i => i.status === 'pending' || i.status === 'ready');
  console.log(`Pendentes: ${pending.length}`);

  const nameIdx = JSON.parse(fs.readFileSync(ARCHIVE_NAME_INDEX, 'utf-8'));
  const jpIdx = JSON.parse(fs.readFileSync(ARCHIVE_JP_INDEX, 'utf-8'));
  console.log(`Indices atuais: name=${Object.keys(nameIdx).length}, jp=${Object.keys(jpIdx).length}`);

  // Filtra seriais que nao estao em nenhum indice
  const missing = pending.filter(i => !nameIdx[i.serial] && !jpIdx[i.serial]);
  console.log(`Sem indice: ${missing.length}`);

  let added = 0;
  const BATCH = 5; // 5 buscas em paralelo
  for (let i = 0; i < missing.length; i += BATCH) {
    const batch = missing.slice(i, i + BATCH);
    const results = await Promise.all(batch.map(async item => {
      try {
        const q = encodeURIComponent(`"${item.serial}"`);
        const url = `https://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=title&rows=5&page=1&output=json&save=yes`;
        const res = await axios.get(url, { timeout: 15000 });
        const docs = res.data?.response?.docs || [];
        if (!docs.length) return null;

        for (const d of docs) {
          try {
            const meta = await axios.get(`https://archive.org/metadata/${d.identifier}`, { timeout: 15000 });
            const files = meta.data?.files || [];
            const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso|chd)$/i.test(f.name) && f.size > 1024 * 1024);
            if (!romFiles.length) continue;
            const best = romFiles.find(f => f.name.toLowerCase().includes(item.serial.toLowerCase())) || romFiles[0];
            return {
              serial: item.serial,
              entry: {
                download_url: `https://archive.org/download/${d.identifier}/${encodeURIComponent(best.name)}`,
                name: d.title,
                size: parseInt(best.size) || 0,
                collection: d.identifier,
                file: best.name
              }
            };
          } catch (e) { continue; }
        }
        return null;
      } catch (e) { return null; }
    }));

    for (const r of results) {
      if (r) {
        // Determina se e JP ou EU pelo serial
        if (r.serial.startsWith('SLPM') || r.serial.startsWith('SLPS') || r.serial.startsWith('SCPS')) {
          jpIdx[r.serial] = {
            collection: r.entry.collection,
            file: r.entry.file,
            url: r.entry.download_url,
            name: r.entry.name,
            size: r.entry.size
          };
        } else {
          nameIdx[r.serial] = r.entry;
        }
        added++;
      }
    }

    // Salva a cada 50 itens
    if (added > 0 && (i + BATCH) % 50 === 0) {
      fs.writeFileSync(ARCHIVE_NAME_INDEX, JSON.stringify(nameIdx, null, 2));
      fs.writeFileSync(ARCHIVE_JP_INDEX, JSON.stringify(jpIdx, null, 2));
      console.log(`Progresso: ${i + BATCH}/${missing.length}, adicionados: ${added}`);
    }
  }

  // Salva no final
  fs.writeFileSync(ARCHIVE_NAME_INDEX, JSON.stringify(nameIdx, null, 2));
  fs.writeFileSync(ARCHIVE_JP_INDEX, JSON.stringify(jpIdx, null, 2));
  console.log(`Concluido: ${added} novos itens nos indices`);
}

main().catch(e => { console.error('Erro:', e.message); process.exit(1); });
