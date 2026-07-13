const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.romsretro;

module.exports = {
  name: 'romsretro',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 7,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('romsretro', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
