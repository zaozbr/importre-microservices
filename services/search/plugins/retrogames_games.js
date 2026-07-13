const { genericSiteSearch } = require('./generic_search');
const sites = require('./web_sites');
const cfg = sites.retrogames_games;

module.exports = {
  name: 'retrogames.games',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 21,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('retrogames.games', cfg.base, cfg.search, cfg.patterns, serial, title);
  }
};
