// Busca de ROMs PSX em sites de torrent (Pirate Bay, 1337x, Nyaa)
// Usa APIs publicas e scraping leve para encontrar magnet links
const axios = require('axios');
const { buildSource } = require('./_base');

const TIMEOUT = 20000;
const USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36';

// 1. Pirate Bay via API proxy (apibay.org)
async function searchPirateBay(serial, title) {
  if (!title || title.length < 3) return [];
  try {
    // Limpar titulo - remover parenteses e colchetes
    const cleanTitle = title.replace(/\[.*?\]|\(.*?\)/g, '').trim().replace(/\s+/g, ' ');
    // Pirate Bay nao suporta OR - usar apenas o titulo + PSX
    const q = encodeURIComponent(`${cleanTitle} PSX`);
    const url = `https://apibay.org/q.php?q=${q}`;
    const res = await axios.get(url, { timeout: TIMEOUT, headers: { 'User-Agent': USER_AGENT } });
    const torrents = res.data || [];
    const results = [];
    for (const t of torrents.slice(0, 5)) {
      if (t.id === '0' || !t.info_hash) continue;
      const size = parseInt(t.size) || 0;
      if (size < 1024 * 1024) continue; // > 1MB
      const magnet = `magnet:?xt=urn:btih:${t.info_hash}&dn=${encodeURIComponent(t.name)}&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80`;
      results.push(buildSource('piratebay', magnet, t.name, {
        size,
        seeders: parseInt(t.seeders) || 0,
        leechers: parseInt(t.leechers) || 0
      }));
    }
    return results;
  } catch { return []; }
}

// 2. Nyaa (para jogos JP)
async function searchNyaa(serial, title) {
  if (!title || title.length < 3) return [];
  try {
    const q = encodeURIComponent(`${title} psx`);
    const url = `https://nyaa.si/?f=0&c=0_0&q=${q}&s=seeders&o=desc`;
    const res = await axios.get(url, {
      timeout: TIMEOUT,
      headers: { 'User-Agent': USER_AGENT, 'Accept-Language': 'en-US,en;q=0.9' }
    });
    const html = res.data;
    const magnetMatches = html.match(/magnet:\?xt=urn:btih:[a-fA-F0-9]{40}[^"'\s]*/g) || [];
    const results = [];
    for (const magnet of magnetMatches.slice(0, 3)) {
      const hashMatch = magnet.match(/btih:([a-fA-F0-9]{40})/);
      if (!hashMatch) continue;
      results.push(buildSource('nyaa', magnet, `nyaa:${hashMatch[1].substring(0, 8)}`, {}));
    }
    return results;
  } catch { return []; }
}

// 4. Archive.org torrent search (procura torrents dentro de colecoes) via Tor
async function searchArchiveTorrent(serial, title) {
  if (!title || title.length < 3) return [];
  try {
    const { getArchiveHeaders } = require('../../../shared/archive_auth');
    const { getAxiosProxyConfig } = require('../../../shared/tor_proxy');
    const hdrs = getArchiveHeaders();
    const cleanTitle = title.replace(/\[.*?\]|\(.*?\)/g, '').trim();
    if (cleanTitle.length < 3) return [];
    const q = encodeURIComponent(`(${cleanTitle}) AND mediatype:software AND format:Archive BitTorrent`);
    const url = `https://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&rows=5&output=json`;
    const res = await axios.get(url, { timeout: 45000, headers: hdrs, ...getAxiosProxyConfig(url) });
    const docs = res.data?.response?.docs || [];
    const results = [];
    for (const d of docs) {
      const metaUrl = `https://archive.org/metadata/${d.identifier}`;
      const meta = await axios.get(metaUrl, { timeout: 30000, headers: hdrs, ...getAxiosProxyConfig(metaUrl) });
      const torrentFile = (meta.data?.files || []).find(f => f.name.endsWith('.torrent'));
      if (torrentFile) {
        const torrentUrl = `https://archive.org/download/${d.identifier}/${torrentFile.name}`;
        results.push(buildSource('archive.org-torrent', torrentUrl, d.identifier, { size: parseInt(torrentFile.size) || 0 }));
      }
    }
    return results;
  } catch { return []; }
}

// 5. Solid Torrents (API JSON)
async function searchSolidTorrents(serial, title) {
  if (!title || title.length < 3) return [];
  try {
    const cleanTitle = title.replace(/\[.*?\]|\(.*?\)/g, '').trim();
    const q = encodeURIComponent(`${cleanTitle} psx`);
    const url = `https://api.solidtorrents.to/v1/search?q=${q}`;
    const res = await axios.get(url, { timeout: TIMEOUT, headers: { 'User-Agent': USER_AGENT } });
    const torrents = res.data?.results || [];
    const results = [];
    for (const t of torrents.slice(0, 5)) {
      if (!t.infohash) continue;
      const magnet = `magnet:?xt=urn:btih:${t.infohash}&dn=${encodeURIComponent(t.title)}&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337`;
      results.push(buildSource('solidtorrents', magnet, t.title, {
        size: parseInt(t.size) || 0,
        seeders: parseInt(t.swarm?.seeders) || 0
      }));
    }
    return results;
  } catch { return []; }
}

module.exports = {
  name: 'torrent_search',
  matchType: 'serial',
  needsMultiChunk: false,
  priority: 60,
  enabled: true,
  async search(serial, title) {
    // Buscar em paralelo em todas as fontes torrent
    const [pb, nyaa, archT, solid] = await Promise.all([
      searchPirateBay(serial, title),
      searchNyaa(serial, title),
      searchArchiveTorrent(serial, title),
      searchSolidTorrents(serial, title)
    ]);
    const all = [...pb, ...nyaa, ...archT, ...solid];
    all.sort((a, b) => (b.metadata?.seeders || 0) - (a.metadata?.seeders || 0));
    return all;
  }
};
