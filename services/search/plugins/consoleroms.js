const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.consoleroms;

module.exports = {
  name: 'consoleroms',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 13,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('consoleroms', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
