const { loadJson, buildSource } = require('./_base');

module.exports = {
  name: 'myrient',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 30,
  enabled: true,
  search(serial, title) {
    const results = loadJson('myrient_results.json');
    if (!Array.isArray(results)) return [];
    const item = results.find(r => r.serial === serial);
    if (!item || !item.url) return [];
    return [buildSource('myrient', item.url, title || serial)];
  }
};
