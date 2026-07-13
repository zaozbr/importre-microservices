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
    if (!target || target.length < 3) return [];
    
    const results = [];
    const scored = [];
    
    for (const item of Object.values(crData)) {
      if (!item.norm || !item.url) continue;
      
      // Validacao rigorosa: score de similaridade
      const score = titleScore(target, item.norm);
      if (score >= 0.7) { // 70%+ de similaridade
        scored.push({ item, score });
      }
    }
    
    // Ordena por score (maior primeiro)
    scored.sort((a, b) => b.score - a.score);
    
    for (const { item, score } of scored.slice(0, 3)) {
      results.push(buildSource('coolrom', `https://coolrom.com.au${item.url}`, item.name, { score }));
    }
    return results;
  }
};
