const axios = require('axios');
const { buildSource } = require('./_base');

module.exports = {
  name: 'google-fallback',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 100,
  enabled: true,
  async search(serial, title) {
    const query = encodeURIComponent(`"${serial}" psx rom download 7z zip`);
    const engines = [
      `https://www.bing.com/search?q=${query}`,
      `https://html.duckduckgo.com/html/?q=${query}`
    ];
    const patterns = [
      '<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]{10,120})</a>',
      '<a[^>]+href="(/[^"]+)"[^>]*>([^<]{10,120})</a>'
    ];
    for (const url of engines) {
      try {
        const res = await axios.get(url, {
          timeout: 15000,
          headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }
        });
        const html = res.data;
        const results = [];
        for (const pattern of patterns) {
          const re = new RegExp(pattern, 'gi');
          let m;
          while ((m = re.exec(html)) !== null) {
            let href = m[1].replace(/&amp;/g, '&');
            if (href.startsWith('/')) {
              const base = url.split('/').slice(0, 3).join('/');
              href = base + href;
            }
            const text = (m[2] || '').trim().replace(/\s+/g, ' ');
            if (/google|bing|duckduckgo|facebook|twitter|reddit|wikipedia/i.test(href)) continue;
            if (text.length > 5) results.push(buildSource('google-fallback', href, text));
          }
        }
        if (results.length) return results.slice(0, 5);
      } catch (e) { /* ignore */ }
    }
    return [];
  }
};
