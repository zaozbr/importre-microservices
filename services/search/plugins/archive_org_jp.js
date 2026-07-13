const axios = require('axios');
const { loadJson, buildSource } = require('./_base');

module.exports = {
  name: 'archive.org-jp',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 2,
  enabled: true,
  async search(serial, title) {
    // 1. Indice local JP (rapido)
    const idx = loadJson('archive_jp_index.json');
    const info = idx[serial];
    if (info && info.url) {
      return [buildSource('archive.org-jp', info.url, info.file || info.name || title || serial, { size: info.size })];
    }
    if (info && info.collection && info.file) {
      return [buildSource('archive.org-jp', `https://archive.org/download/${info.collection}/${encodeURIComponent(info.file)}`, info.file, { size: info.size })];
    }

    // 2. Busca online no archive.org por serial JP
    try {
      const q = encodeURIComponent(`"${serial}" AND (collection:psx OR collection:redump OR collection:sony_playstation)`);
      const url = `https://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=title&rows=10&page=1&output=json&save=yes`;
      const res = await axios.get(url, { timeout: 12000 });
      const docs = res.data?.response?.docs || [];
      if (!docs.length) return [];
      const metaPromises = docs.map(async d => {
        try {
          const meta = await axios.get(`https://archive.org/metadata/${d.identifier}`, { timeout: 12000 });
          const files = meta.data?.files || [];
          // Procura por arquivo que contenha o serial no nome
          const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso|chd)$/i.test(f.name) && f.size > 1024 * 1024);
          if (!romFiles.length) return null;
          const best = romFiles.find(f => f.name.toLowerCase().includes(serial.toLowerCase())) || romFiles[0];
          return buildSource('archive.org-jp', `https://archive.org/download/${d.identifier}/${encodeURIComponent(best.name)}`, d.title, { size: best.size });
        } catch (e) { return null; }
      });
      const sources = (await Promise.all(metaPromises)).filter(Boolean);
      return sources;
    } catch (e) {
      return [];
    }
  }
};
