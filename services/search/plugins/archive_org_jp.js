const axios = require('axios');
const { loadJson, buildSource } = require('./_base');
const { getArchiveHeaders } = require('../../../shared/archive_auth');
const { getAxiosProxyConfig } = require('../../../shared/tor_proxy');

const SITE = 'archive.org-jp';

module.exports = {
  name: SITE,
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 2,
  enabled: true,
  async search(serial, title) {
    // 1. Indice local JP (rapido)
    const idx = loadJson('archive_jp_index.json');
    const info = idx[serial];
    if (info && info.url) {
      return [buildSource(SITE, info.url, info.file || info.name || title || serial, { size: info.size })];
    }
    if (info && info.collection && info.file) {
      return [buildSource(SITE, `https://archive.org/download/${info.collection}/${encodeURIComponent(info.file)}`, info.file, { size: info.size })];
    }

    // 2. Indice dinamico (gerado por reindex_missing.js)
    const dynIdx = loadJson('archive_jp_dynamic.json');
    const dynInfo = dynIdx[serial];
    if (dynInfo && dynInfo.collection && dynInfo.file) {
      return [buildSource(SITE, `https://archive.org/download/${dynInfo.collection}/${encodeURIComponent(dynInfo.file)}`, dynInfo.file, { size: dynInfo.size })];
    }

    // 3. Busca online no archive.org por serial via Tor (HTTPS - mais rapido que HTTP)
    try {
      const hdrs = getArchiveHeaders();
      // Buscar sem aspas (full-text) - o serial pode estar no nome do arquivo
      const q = encodeURIComponent(`${serial} AND (collection:psx OR collection:redump OR collection:sony_playstation OR collection:softwarelibrary_psx OR mediatype:software)`);
      const url = `https://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=title&rows=10&page=1&output=json`;
      const res = await axios.get(url, { timeout: 45000, headers: hdrs, ...getAxiosProxyConfig(url) });
      const docs = res.data?.response?.docs || [];
      if (!docs.length) return [];
      const metaPromises = docs.map(async d => {
        try {
          const metaUrl = `https://archive.org/metadata/${d.identifier}`;
          const meta = await axios.get(metaUrl, { timeout: 30000, headers: hdrs, ...getAxiosProxyConfig(metaUrl) });
          const files = meta.data?.files || [];
          const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso|chd)$/i.test(f.name) && f.size > 1024 * 1024);
          if (!romFiles.length) return null;
          const best = romFiles.find(f => f.name.toLowerCase().includes(serial.toLowerCase())) || romFiles[0];
          return buildSource(SITE, `https://archive.org/download/${d.identifier}/${encodeURIComponent(best.name)}`, d.title, { size: best.size });
        } catch { return null; }
      });
      const sources = (await Promise.all(metaPromises)).filter(Boolean);
      return sources;
    } catch {
      return [];
    }
  }
};
