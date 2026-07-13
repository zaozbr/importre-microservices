const fs = require('fs');
const path = require('path');
const { STATE_DIR } = require('../../../shared/config');

const cache = {};

function loadJson(name) {
  if (cache[name]) return cache[name];
  const file = path.join(STATE_DIR, name);
  try {
    if (fs.existsSync(file)) {
      cache[name] = JSON.parse(fs.readFileSync(file, 'utf-8'));
      return cache[name];
    }
  } catch (e) {
    console.error('Erro lendo', file, e.message);
  }
  cache[name] = {};
  return cache[name];
}

function normalize(str) {
  return (str || '').toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
}

function titleScore(a, b) {
  const na = normalize(a);
  const nb = normalize(b);
  if (!na || !nb) return 0;
  if (na === nb) return 1;
  const wa = na.split(' ').filter(Boolean);
  const wb = nb.split(' ').filter(Boolean);
  if (!wa.length || !wb.length) return 0;
  const common = wa.filter(w => wb.includes(w)).length;
  const baseScore = common / Math.max(wa.length, wb.length);
  // Bonus: se todas as palavras do menor estao no maior (subset)
  const minLen = Math.min(wa.length, wb.length);
  if (common === minLen) {
    // Subset completo - bonus proporcional
    return Math.min(1, baseScore + 0.25);
  }
  return baseScore;
}

function buildSource(site, url, title, extra = {}) {
  return { site, url, title, ...extra };
}

module.exports = { loadJson, normalize, titleScore, buildSource };
