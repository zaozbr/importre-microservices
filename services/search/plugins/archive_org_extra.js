// archive.org-extra: busca em coleções privadas/restritas do archive.org
// Requer login (cookies) para acessar coleções como psx-roms-archive
const axios = require('axios');
const { loadJson, buildSource } = require('./_base');
const { getArchiveHeaders } = require('../../../shared/archive_auth');

// Coleções extra conhecidas (requerem login)
const EXTRA_COLLECTIONS = [
  'psx-roms-archive',
  'CuratedPSXRedumpCHDs',
  'psx-ntscj-chd-zstd',
  'Sony_PlayStation_USA_CHD',
  'Sony_PlayStation_Europe_CHD',
  'RedumpSonyPlayStation',
  'psx-redump-collection'
];

module.exports = {
  name: 'archive.org-extra',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 8,
  enabled: true,
  async search(serial, title) {
    const hdrs = getArchiveHeaders();
    if (!hdrs['Cookie']) {
      // Sem cookies de login, tenta só o cache local
      const extra = loadJson('extra_index.json');
      const smart = loadJson('smart_index.json');
      const sources = [];
      const seen = new Set();
      for (const idx of [extra, smart]) {
        const bySerial = idx?.by_serial || idx || {};
        const items = bySerial[serial] || [];
        for (const item of items) {
          if (!item.collection || !item.filename) continue;
          const url = `http://archive.org/download/${item.collection}/${encodeURIComponent(item.filename)}`;
          if (seen.has(url)) continue;
          seen.add(url);
          sources.push(buildSource('archive.org-extra', url, item.filename, { size: parseInt(item.size) || undefined }));
          if (sources.length >= 3) return sources;
        }
      }
      return sources;
    }

    // Com cookies: busca online nas coleções extra
    const sources = [];
    const seen = new Set();

    // 1. Cache local primeiro (rapido)
    const extra = loadJson('extra_index.json');
    const smart = loadJson('smart_index.json');
    for (const idx of [extra, smart]) {
      const bySerial = idx?.by_serial || idx || {};
      const items = bySerial[serial] || [];
      for (const item of items) {
        if (!item.collection || !item.filename) continue;
        const url = `http://archive.org/download/${item.collection}/${encodeURIComponent(item.filename)}`;
        if (seen.has(url)) continue;
        seen.add(url);
        sources.push(buildSource('archive.org-extra', url, item.filename, { size: parseInt(item.size) || undefined }));
        if (sources.length >= 5) return sources;
      }
    }

    // 2. Busca online nas coleções extra (com login)
    try {
      const q = encodeURIComponent(`"${serial}" AND (${EXTRA_COLLECTIONS.map(c => `collection:${c}`).join(' OR ')})`);
      const url = `https://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=title&rows=15&page=1&output=json&save=yes`;
      const res = await axios.get(url, { timeout: 15000, headers: hdrs });
      const docs = res.data?.response?.docs || [];
      if (!docs.length) return sources;

      const metaPromises = docs.map(async d => {
        try {
          const meta = await axios.get(`https://archive.org/metadata/${d.identifier}`, { timeout: 15000, headers: hdrs });
          const files = meta.data?.files || [];
          const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso|chd)$/i.test(f.name) && f.size > 1024 * 1024);
          if (!romFiles.length) return null;
          const best = romFiles.find(f => f.name.toLowerCase().includes(serial.toLowerCase())) || romFiles[0];
          const dlUrl = `https://archive.org/download/${d.identifier}/${encodeURIComponent(best.name)}`;
          if (seen.has(dlUrl)) return null;
          seen.add(dlUrl);
          return buildSource('archive.org-extra', dlUrl, d.title, { size: parseInt(best.size) || undefined });
        } catch (e) { return null; }
      });
      const onlineSources = (await Promise.all(metaPromises)).filter(Boolean);
      sources.push(...onlineSources);
    } catch (e) {
      // ignora erro de rede
    }

    return sources.slice(0, 5);
  }
};
