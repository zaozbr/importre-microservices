const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.freeroms;

module.exports = {
  name: 'freeroms',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 32,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('freeroms', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
