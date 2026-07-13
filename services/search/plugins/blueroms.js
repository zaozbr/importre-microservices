const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.blueroms;

module.exports = {
  name: 'blueroms',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 31,
  enabled: false, // so torrent - nao serve para HTTP
  search(serial, title) {
    return genericSiteSearch('blueroms', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
