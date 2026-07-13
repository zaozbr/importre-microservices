const { loadJson, buildSource } = require('./_base');

module.exports = {
  name: 'romsdl',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 16,
  enabled: true,
  search(serial, title) {
    const cache = loadJson('romsdl_cache.json');
    const path = cache[serial];
    if (!path) return [];
    return [buildSource('romsdl', `https://www.romsdl.com${path}`, title || serial)];
  }
};
