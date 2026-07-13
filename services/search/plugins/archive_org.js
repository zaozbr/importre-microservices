const axios = require('axios');
const { loadJson, buildSource } = require('./_base');

module.exports = {
  name: 'archive.org',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 1,
  enabled: true,
  async search(serial, title) {
    // 1. Indice local de nomes (cobertura EU/PAL)
    const nameIdx = loadJson('archive_name_index.json');
    const local = nameIdx[serial];
    if (local && local.download_url) {
      return [buildSource('archive.org', local.download_url, local.name || title || serial, { size: local.size })];
    }

    // 2. Busca online no archive.org
    try {
      const q = encodeURIComponent(`"${serial}"`);
      const url = `https://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=title&rows=10&page=1&output=json&save=yes`;
      const res = await axios.get(url, { timeout: 20000 });
      const docs = res.data?.response?.docs || [];
      const sources = [];
      for (const d of docs) {
        try {
          const meta = await axios.get(`https://archive.org/metadata/${d.identifier}`, { timeout: 15000 });
          const files = meta.data?.files || [];
          const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso|chd)$/i.test(f.name) && f.size > 1024 * 1024);
          if (romFiles.length) {
            const best = romFiles.find(f => f.name.toLowerCase().includes(serial.toLowerCase())) || romFiles[0];
            sources.push(buildSource('archive.org', `https://archive.org/download/${d.identifier}/${encodeURIComponent(best.name)}`, d.title, { size: best.size }));
          }
        } catch (e) { /* ignore */ }
      }
      return sources;
    } catch (e) {
      return [];
    }
  }
};
