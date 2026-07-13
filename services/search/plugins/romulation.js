const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.romulation;

module.exports = {
  name: 'romulation',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 4,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('romulation', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
