const { loadJson, buildSource } = require('./_base');

module.exports = {
  name: 'archive.org-jp',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 2,
  enabled: true,
  search(serial, title) {
    const idx = loadJson('archive_jp_index.json');
    const info = idx[serial];
    if (!info) return [];
    return [buildSource('archive.org-jp', `https://archive.org/download/${info.collection}/${encodeURIComponent(info.file)}`, info.file, { size: info.size })];
  }
};
