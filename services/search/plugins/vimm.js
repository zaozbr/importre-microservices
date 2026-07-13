const { loadJson, buildSource } = require('./_base');

module.exports = {
  name: 'vimm',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 4,
  enabled: true,
  search(serial, title) {
    const cache = loadJson('vimm_cache.json');
    const id = cache[serial];
    if (!id) return [];
    // URL da página do jogo - o resolver extrai mediaId do HTML
    // e usa mirror archival.cat/PS1/{mediaId}.7z ou POST dl3.vimm.net
    return [buildSource('vimm', `https://vimm.net/vault/${id}`, title || serial)];
  }
};
