const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.retromania;

module.exports = {
  name: 'retromania',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 15,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('retromania', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
