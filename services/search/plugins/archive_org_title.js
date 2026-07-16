// Busca por titulo no archive.org via Tor (HTTPS) ou HTTP fallback
// Para seriais que nao estao no indice local, busca por titulo no archive.org
const axios = require('axios');
const { buildSource } = require('./_base');
const { getArchiveHeaders } = require('../../../shared/archive_auth');
const { getAxiosProxyConfig } = require('../../../shared/tor_proxy');

module.exports = {
  name: 'archive_org_title',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 50,
  enabled: true,
  async search(serial, title) {
    if (!title || title.length < 3) return [];
    try {
      const hdrs = getArchiveHeaders();
      const cleanTitle = title.replace(/\[.*?\]|\(.*?\)/g, '').trim().replace(/\s+/g, ' ');
      if (cleanTitle.length < 3) return [];

      // Buscar por titulo no archive.org - colecoes PSX + mediatype software
      const q = encodeURIComponent(`(${cleanTitle}) AND (collection:psx OR collection:redump OR collection:sony_playstation OR collection:softwarelibrary_psx OR mediatype:software)`);
      const url = `https://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=downloads&rows=15&page=1&output=json`;
      const res = await axios.get(url, { timeout: 45000, headers: hdrs, ...getAxiosProxyConfig(url) });
      const docs = res.data?.response?.docs || [];
      if (!docs.length) return [];

      // Para cada item encontrado, buscar arquivos de ROM
      const metaPromises = docs.map(async d => {
        try {
          const metaUrl = `https://archive.org/metadata/${d.identifier}`;
          const meta = await axios.get(metaUrl, { timeout: 30000, headers: hdrs, ...getAxiosProxyConfig(metaUrl) });
          const files = meta.data?.files || [];
          const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso|chd|ecm)$/i.test(f.name) && f.size > 1024 * 1024);
          if (!romFiles.length) return null;
          const titleLower = (title || '').toLowerCase();
          const best = romFiles.find(f => f.name.toLowerCase().includes(titleLower.substring(0, 10).toLowerCase())) || romFiles[0];
          return buildSource('archive.org', `https://archive.org/download/${d.identifier}/${encodeURIComponent(best.name)}`, d.title, { size: best.size });
        } catch { return null; }
      });
      const sources = (await Promise.all(metaPromises)).filter(Boolean);
      return sources;
    } catch {
      return [];
    }
  }
};
