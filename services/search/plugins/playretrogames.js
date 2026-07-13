const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.playretrogames;

module.exports = {
  name: 'playretrogames',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 23,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('playretrogames', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
