const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.romsgames;

module.exports = {
  name: 'romsgames',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 14,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('romsgames', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
