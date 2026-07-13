const axios = require('axios');
const { buildSource } = require('./_base');

module.exports = {
  name: 'archive.org',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 1,
  enabled: true,
  async search(serial, title) {
    try {
      const q = encodeURIComponent(`"${serial}"`);
      const url = `http://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=title&rows=10&page=1&output=json&save=yes`;
      const res = await axios.get(url, { timeout: 20000 });
      const docs = res.data?.response?.docs || [];
      const sources = [];
      for (const d of docs) {
        try {
          const meta = await axios.get(`http://archive.org/metadata/${d.identifier}`, { timeout: 15000 });
          const files = meta.data?.files || [];
          const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso)$/i.test(f.name) && f.size > 1024 * 1024);
          if (romFiles.length) {
            const best = romFiles.find(f => f.name.toLowerCase().includes(serial.toLowerCase())) || romFiles[0];
            sources.push(buildSource('archive.org', `http://archive.org/download/${d.identifier}/${encodeURIComponent(best.name)}`, d.title, { size: best.size }));
          }
        } catch (e) { /* ignore */ }
      }
      return sources;
    } catch (e) {
      return [];
    }
  }
};
