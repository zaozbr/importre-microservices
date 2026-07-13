const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.romspure;

module.exports = {
  name: 'romspure',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 18,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('romspure', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
