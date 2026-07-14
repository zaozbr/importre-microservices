// archive.org colecoes Redump PSX (2021-06-04) - ROMs JP em ZIP
// Colecoes divididas por letra: 0-9, A-C, D-F, G-I, J-L, M-O, P-R, S-T, U-W, X-Z
// Busca por titulo (match fuzzy) - so para seriais JP
// URL: https://archive.org/download/{collection}/{nome}.zip
const axios = require('axios');
const { normalize, titleScore, buildSource } = require('./_base');

const HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' };

// 3 colecoes Redump PSX acessiveis (outras sao access-restricted)
const COLLECTIONS = [
  'Redump_PSX_2021_06_04_0-9',
  'Redump_PSX_2021_06_04_A_C',
  'Redump_PSX_2021_06_04_D_F'
];

// Cache: { collection: { files: [...], time: ms } }
const cache = {};
const CACHE_TTL = 3600000; // 1 hora

function cleanTitle(title) {
  if (!title) return '';
  return normalize(title
    .replace(/\(japan\)/gi, '')
    .replace(/\(disc\s*\d+\)/gi, '')
    .replace(/\(v\d+\.\d+\)/gi, '')
    .replace(/\(demo\)/gi, '')
    .replace(/\(beta\)/gi, '')
    .replace(/\(en,ja,fr,de\)/gi, '')
    .replace(/\(playstation the best\)/gi, '')
    .replace(/\(gentei set\)/gi, '')
    .replace(/\(rev \d+\)/gi, '')
    .trim());
}

// Determina qual colecao buscar pela primeira letra do titulo
// Como so 3 colecoes estao acessiveis, mapeia todas para elas
function getCollectionsForTitle(title) {
  if (!title) return COLLECTIONS;
  const first = title.charAt(0).toUpperCase();
  if (first >= '0' && first <= '9') return ['Redump_PSX_2021_06_04_0-9'];
  if (first >= 'A' && first <= 'C') return ['Redump_PSX_2021_06_04_A_C'];
  if (first >= 'D' && first <= 'F') return ['Redump_PSX_2021_06_04_D_F'];
  // G-Z: busca em todas as 3 acessiveis (outras colecoes sao restricted)
  return COLLECTIONS;
}

async function loadCollection(col) {
  const now = Date.now();
  if (cache[col] && now - cache[col].time < CACHE_TTL) return cache[col].files;
  try {
    const url = `https://archive.org/metadata/${col}`;
    const res = await axios.get(url, { headers: HEADERS, timeout: 20000 });
    if (res.data && res.data.files) {
      // Filtra apenas .zip com (Japan) no nome
      const files = res.data.files
        .filter(f => f.name.endsWith('.zip') && /\(japan\)/i.test(f.name))
        .map(f => ({
          name: f.name,
          size: parseInt(f.size) || 0,
          url: `https://archive.org/download/${col}/${encodeURIComponent(f.name)}`
        }));
      cache[col] = { files, time: now };
      return files;
    }
  } catch (e) { /* fallback vazio */ }
  cache[col] = { files: [], time: now };
  return [];
}

module.exports = {
  name: 'archive-redump-jp',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 7,
  enabled: true,
  async search(serial, title) {
    if (!title) return [];
    // So busca para seriais JP
    if (!/^(SLPS|SCPS|SLPM)/.test(serial)) return [];

    const target = cleanTitle(title);
    if (target.length < 3) return [];

    const cols = getCollectionsForTitle(title);
    const allFiles = [];
    for (const col of cols) {
      const files = await loadCollection(col);
      allFiles.push(...files);
    }
    if (!allFiles.length) return [];

    const stopWords = new Set(['the', 'of', 'and', 'a', 'an', 'to', 'in', 'for', 'on', 'at', 'by', 'with', 'from', 'is', 'it', 'this', 'that', 'vol', 'volume']);
    const targetWords = target.split(' ').filter(w => w.length >= 3 && !stopWords.has(w));

    const scored = [];
    for (const f of allFiles) {
      const fName = cleanTitle(f.name.replace(/\.zip$/i, ''));
      let score = titleScore(target, fName);

      if (targetWords.length > 0) {
        const matched = targetWords.filter(w => fName.includes(w)).length;
        if (matched === targetWords.length) {
          score = Math.max(score, 0.85);
        }
      }

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
    return scored.slice(0, 3).map(f =>
      buildSource('archive-redump-jp', f.url, title, { score: f.score, size: f.size })
    );
  }
};
