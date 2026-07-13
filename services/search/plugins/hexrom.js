const { genericSiteSearch } = require('./generic_search');

module.exports = {
  name: 'hexrom',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 12,
  enabled: true,
  search(serial, title) {
    return genericSiteSearch('hexrom', 'https://hexrom.com', 'https://hexrom.com/?s={query}', [
      '<a[^>]+href="(/rom/[^"]+)"[^>]*>([^<]{10,120})</a>'
    ], serial, title);
  }
};
