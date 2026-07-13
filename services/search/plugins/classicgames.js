const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.classicgames;

module.exports = {
  name: 'classicgames',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 20,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('classicgames', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
