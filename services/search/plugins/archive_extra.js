const { loadJson, buildSource } = require('./_base');

module.exports = {
  name: 'archive.org-extra-old',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 10,
  enabled: false,
  search(serial, title) {
    const extra = loadJson('extra_index.json');
    const smart = loadJson('smart_index.json');
    const sources = [];
    const seen = new Set();
    for (const idx of [extra, smart]) {
      const bySerial = idx?.by_serial || idx || {};
      const items = bySerial[serial] || [];
      for (const item of items) {
        if (!item.collection || !item.filename) continue;
        const url = `http://archive.org/download/${item.collection}/${encodeURIComponent(item.filename)}`;
        if (seen.has(url)) continue;
        seen.add(url);
        sources.push(buildSource('archive.org-extra', url, item.filename, { size: parseInt(item.size) || undefined }));
        if (sources.length >= 3) return sources;
      }
    }
    return sources;
  }
};
