const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.retrogames_cc;

module.exports = {
  name: 'retrogames.cc',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 22,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('retrogames.cc', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
