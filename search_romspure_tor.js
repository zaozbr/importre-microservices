const axios = require('axios');
const { SocksProxyAgent } = require('socks-proxy-agent');
const agent = new SocksProxyAgent('socks5://127.0.0.1:9050');

const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.9',
  'Connection': 'keep-alive',
  'Upgrade-Insecure-Requests': '1'
};

async function searchSite(url, query, pattern) {
  try {
    const r = await axios.get(url.replace('{query}', encodeURIComponent(query)), {
      timeout: 30000,
      headers,
      httpAgent: agent,
      httpsAgent: agent
    });
    const h = r.data;
    const matches = [...h.matchAll(new RegExp(pattern, 'gi'))];
    return matches.map(m => ({ url: m[1], title: m[2] ? m[2].trim() : '' }));
  } catch (e) {
    return { error: e.message, status: e.response && e.response.status };
  }
}

async function main() {
  const sites = [
    { name: 'romspure', url: 'https://romspure.cc/?s={query}', pattern: '<a[^>]+href="(/roms/[^"]+)"[^>]*>([^<]+)</a>' },
    { name: 'cdromance', url: 'https://cdromance.com/?s={query}', pattern: '<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>' },
    { name: 'roms2000', url: 'https://www.roms2000.com/?s={query}', pattern: '<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>' }
  ];

  const queries = ['senryaku shougi', 'poketan', 'soukyuu gurentai', 'pacapaca passion'];

  for (const site of sites) {
    console.log('\n=== ' + site.name + ' ===');
    for (const q of queries) {
      const results = await searchSite(site.url, q, site.pattern);
      if (Array.isArray(results)) {
        const filtered = results.filter(r => r.url.includes('/roms/') || r.url.includes('playstation') || r.url.includes('psx'));
        console.log(q, '->', filtered.length, 'results');
        filtered.slice(0, 3).forEach(r => console.log('  ', r.url, r.title));
      } else {
        console.log(q, '->', results.error, results.status);
      }
    }
  }
}
main();
