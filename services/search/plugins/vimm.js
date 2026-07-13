const { loadJson, buildSource } = require('./_base');

module.exports = {
  name: 'vimm',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 4,
  enabled: true,
  search(serial, title) {
    const cache = loadJson('vimm_cache.json');
    const id = cache[serial];
    if (!id) return [];
    return [buildSource('vimm', `https://vimm.net/vault/${id}`, title || serial)];
  }
};
