const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.romspedia;

module.exports = {
  name: 'romspedia',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 8,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('romspedia', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
