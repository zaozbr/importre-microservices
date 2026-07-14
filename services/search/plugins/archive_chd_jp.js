// archive.org colecao chd_psx_jap - 4161 ROMs JP em formato CHD
// Busca por titulo no metadata da colecao (match fuzzy)
// URL: https://archive.org/download/chd_psx_jap/CHD-PSX-JAP/{nome}.chd
const axios = require('axios');
const { normalize, titleScore, buildSource } = require('./_base');
const { getMagnetByCollection } = require('./magnet_cache');

const HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' };
const COLLECTION = 'chd_psx_jap';
const DIR = 'CHD-PSX-JAP';
const META_URL = `https://archive.org/metadata/${COLLECTION}`;

let fileCache = null;
let cacheTime = 0;
const CACHE_TTL = 3600000; // 1 hora

// Normaliza titulo removendo (Japan), (Disc N), etc
function cleanTitle(title) {
  if (!title) return '';
  return normalize(title
    .replace(/\(japan\)/gi, '')
    .replace(/\(disc\s*\d+\)/gi, '')
    .replace(/\(v\d+\.\d+\)/gi, '')
    .replace(/\(demo\)/gi, '')
    .replace(/\(beta\)/gi, '')
    .trim());
}

async function loadFiles() {
  if (fileCache && Date.now() - cacheTime < CACHE_TTL) return fileCache;
  try {
    const res = await axios.get(META_URL, { headers: HEADERS, timeout: 20000 });
    if (res.data && res.data.files) {
      // Filtra apenas .chd no diretorio CHD-PSX-JAP
      fileCache = res.data.files.filter(f =>
        f.name.endsWith('.chd') &&
        f.name.startsWith(DIR + '/')
      ).map(f => ({
        name: f.name.replace(DIR + '/', ''),
        size: parseInt(f.size) || 0,
        url: `https://archive.org/download/${COLLECTION}/${encodeURIComponent(f.name).replace(/%2F/g, '/')}`
      }));
      cacheTime = Date.now();
      return fileCache;
    }
  } catch (e) { /* fallback vazio */ }
  return [];
}

module.exports = {
  name: 'archive-chd-jp',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 8,
  enabled: true,
  async search(serial, title) {
    if (!title) return [];
    // So busca para seriais JP
    if (!/^(SLPS|SCPS|SLPM)/.test(serial)) return [];

    const files = await loadFiles();
    if (!files.length) return [];

    const target = cleanTitle(title);
    if (target.length < 3) return [];

    // Extrai palavras-chave do titulo
    const stopWords = new Set(['the', 'of', 'and', 'a', 'an', 'to', 'in', 'for', 'on', 'at', 'by', 'with', 'from', 'is', 'it', 'this', 'that', 'vol', 'volume']);
    const targetWords = target.split(' ').filter(w => w.length >= 3 && !stopWords.has(w));

    const scored = [];
    for (const f of files) {
      const fName = cleanTitle(f.name.replace(/\.chd$/i, ''));
      let score = titleScore(target, fName);

      // Bonus: todas as palavras-chave presentes
      if (targetWords.length > 0) {
        const matched = targetWords.filter(w => fName.includes(w)).length;
        if (matched === targetWords.length) {
          score = Math.max(score, 0.85);
        }
      }

      // Penaliza discos errados
      const targetDisc = title.match(/\(disc\s*(\d+)\)/i);
      const fileDisc = f.name.match(/\(disc\s*(\d+)\)/i);
      if (targetDisc && fileDisc && targetDisc[1] !== fileDisc[1]) {
        score *= 0.3;
      }

      if (score >= 0.6) {
        scored.push({ ...f, score });
      }
    }

    scored.sort((a, b) => b.score - a.score);
    const results = scored.slice(0, 3).map(f =>
      buildSource('archive-chd-jp', f.url, title, { score: f.score, size: f.size })
    );
    const magnet = getMagnetByCollection(COLLECTION);
    if (magnet) {
      results.push(buildSource('archive-chd-jp-torrent', magnet, title, { score: 0.8, size: 0 }));
    }
    return results;
  }
};
