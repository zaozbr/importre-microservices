const { loadJson, normalize, titleScore, buildSource } = require('./_base');

module.exports = {
  name: 'retroiso',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 6,
  enabled: true,
  search(serial, title) {
    const cache = loadJson('retroiso_cache.json');
    const target = normalize(title || serial);
    const results = [];
    for (const [name, url] of Object.entries(cache)) {
      if (normalize(name).includes(target) || target.includes(normalize(name))) {
        results.push(buildSource('retroiso', url, name));
        if (results.length >= 2) break;
      }
    }
    return results;
  }
};
