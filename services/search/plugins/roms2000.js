const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.roms2000;

module.exports = {
  name: 'roms2000',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 19,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('roms2000', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
