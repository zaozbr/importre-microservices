const axios = require('axios');
const { SocksProxyAgent } = require('socks-proxy-agent');

const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.9',
  'Accept-Encoding': 'gzip, deflate, br',
  'Connection': 'keep-alive',
  'Upgrade-Insecure-Requests': '1'
};

async function searchRomspure(query) {
  try {
    const r = await axios.get('https://romspure.cc/?s=' + encodeURIComponent(query), {
      timeout: 15000,
      headers
    });
    const h = r.data;
    const matches = [...h.matchAll(/<a[^>]+href="(\/roms\/[^"]+)"[^>]*>([^<]+)<\/a>/gi)];
    return matches.map(m => ({ url: m[1], title: m[2].trim() }));
  } catch (e) {
    return { error: e.message, status: e.response && e.response.status };
  }
}

async function main() {
  const queries = process.argv.slice(2);
  if (queries.length === 0) {
    console.log('Usage: node search_romspure.js <query1> <query2> ...');
    return;
  }
  for (const q of queries) {
    const results = await searchRomspure(q);
    if (Array.isArray(results)) {
      console.log(q, '->', results.length, 'results');
      results.forEach(r => console.log('  ', r.url, r.title));
    } else {
      console.log(q, '->', results.error, results.status);
    }
  }
}
main();
