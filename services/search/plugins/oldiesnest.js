const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.oldiesnest;

module.exports = {
  name: 'oldiesnest',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 24,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('oldiesnest', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
