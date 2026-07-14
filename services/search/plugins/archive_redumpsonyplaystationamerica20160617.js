// Auto-gerado por _source_hunter.js para colecao archive.org: RedumpSonyPlayStationAmerica20160617
const axios = require('axios');
const { normalize, titleScore, buildSource } = require('./_base');
const { getMagnetByCollection } = require('./magnet_cache');

const HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' };
const COLLECTION = 'RedumpSonyPlayStationAmerica20160617';
const cache = { files: null, time: 0 };
const CACHE_TTL = 3600000;

function cleanTitle(t) {
  if (!t) return '';
  return normalize(t
    .replace(/\(japan\)/gi, '').replace(/\(disc\s*\d+\)/gi, '')
    .replace(/\(en,ja,fr,de\)/gi, '').replace(/\(playstation the best\)/gi, '')
    .replace(/\(rev \d+\)/gi, '').replace(/\(demo\)/gi, '')
    .replace(/\(beta\)/gi, '').replace(/\(gentei set\)/gi, '')
    .trim());
}

async function loadFiles() {
  const now = Date.now();
  if (cache.files && now - cache.time < CACHE_TTL) return cache.files;
  try {
    const res = await axios.get(`https://archive.org/metadata/${COLLECTION}`, { headers: HEADERS, timeout: 60000 });
    if (res.data && res.data.files) {
      cache.files = res.data.files
        .filter(f => /\.(zip|7z|chd|bin|iso)$/i.test(f.name))
        .map(f => ({
          name: f.name,
          size: parseInt(f.size) || 0,
          url: `https://archive.org/download/${COLLECTION}/${encodeURIComponent(f.name)}`
        }));
      cache.time = now;
      return cache.files;
    }
  } catch (e) { /* fallback */ }
  cache.files = [];
  cache.time = now;
  return cache.files;
}

module.exports = {
  name: 'archive-redumpsonyplaystationamerica20160617',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 6,
  enabled: true,
  async search(serial, title) {
    if (!title) return [];
    const target = cleanTitle(title);
    if (target.length < 3) return [];
    const files = await loadFiles();
    if (!files.length) return [];
    const stopWords = new Set(['the', 'of', 'and', 'a', 'an', 'to', 'in', 'for', 'on', 'at', 'by', 'with', 'from']);
    const targetWords = target.split(' ').filter(w => w.length >= 3 && !stopWords.has(w));
    const scored = [];
    for (const f of files) {
      const fName = cleanTitle(f.name.replace(/\.(zip|7z|chd|bin|iso)$/i, ''));
      let score = titleScore(target, fName);
      if (targetWords.length > 0) {
        const matched = targetWords.filter(w => fName.includes(w)).length;
        if (matched === targetWords.length) score = Math.max(score, 0.85);
      }
      const targetDisc = title.match(/\(disc\s*(\d+)\)/i);
      const fileDisc = f.name.match(/\(disc\s*(\d+)\)/i);
      if (targetDisc && fileDisc && targetDisc[1] !== fileDisc[1]) score *= 0.3;
      if (score >= 0.6) scored.push({ ...f, score });
    }
    scored.sort((a, b) => b.score - a.score);
    const results = scored.slice(0, 3).map(f =>
      buildSource('archive-redumpsonyplaystationamerica20160617', f.url, title, { score: f.score, size: f.size })
    );
    const magnet = getMagnetByCollection(COLLECTION);
    if (magnet) {
      results.push(buildSource('archive-redumpsonyplaystationamerica20160617-torrent', magnet, title, { score: 0.8, size: 0 }));
    }
    return results;
  }
};
