const { loadJson, buildSource } = require('./_base');

module.exports = {
  name: 'retrostic',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 5,
  enabled: true,
  search(serial, title) {
    const cache = loadJson('retrostic_cache.json');
    const path = cache[serial];
    if (!path) return [];
    return [buildSource('retrostic', `https://www.retrostic.com${path}`, title || serial)];
  }
};
