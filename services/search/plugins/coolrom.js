const { loadJson, normalize, titleScore, buildSource } = require('./_base');

module.exports = {
  name: 'coolrom',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 3,
  enabled: true,
  search(serial, title) {
    const data = loadJson('coolrom_index.json');
    const crData = data.cr_data || data;
    const target = normalize(title || serial);
    const results = [];
    for (const item of Object.values(crData)) {
      if (!item.norm || !item.url) continue;
      if (item.norm.includes(target) || target.includes(item.norm)) {
        results.push(buildSource('coolrom', `https://coolrom.com.au${item.url}`, item.name));
        if (results.length >= 3) break;
      }
    }
    return results;
  }
};
