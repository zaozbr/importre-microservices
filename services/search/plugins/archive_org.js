const axios = require('axios');
const { loadJson, buildSource } = require('./_base');
const { getArchiveHeaders } = require('../../../shared/archive_auth');
const { getAxiosProxyConfig } = require('../../../shared/tor_proxy');

const SITE = 'archive.org';

module.exports = {
  name: 'archive.org',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 1,
  enabled: true,
  async search(serial, title) {
    // 1. Indice local de nomes (cobertura EU/PAL)
    const nameIdx = loadJson('archive_name_index.json');
    const local = nameIdx[serial];
    if (local && local.download_url) {
      return [buildSource(SITE, local.download_url, local.name || title || serial, { size: local.size })];
    }

    // 2. Indice JP
    const jpIdx = loadJson('archive_jp_index.json');
    const jp = jpIdx[serial];
    if (jp && jp.url) {
      return [buildSource(SITE, jp.url, jp.name || title || serial, { size: jp.size })];
    }

    // 3. Indice dinamico (gerado por reindex_missing.js)
    const dynIdx = loadJson('archive_jp_dynamic.json');
    const dyn = dynIdx[serial];
    if (dyn && dyn.collection && dyn.file) {
      return [buildSource(SITE, `https://archive.org/download/${dyn.collection}/${encodeURIComponent(dyn.file)}`, dyn.file, { size: dyn.size })];
    }

    // 4. Busca online no archive.org via Tor (HTTPS - mais rapido que HTTP)
    try {
      const hdrs = getArchiveHeaders();
      // Buscar sem aspas (full-text) para cobrir casos onde o serial esta no nome do arquivo
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
