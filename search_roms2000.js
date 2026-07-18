const axios = require('axios');
const { SocksProxyAgent } = require('socks-proxy-agent');
const agent = new SocksProxyAgent('socks5://127.0.0.1:9050');

const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9'
};

async function checkUrl(url) {
  try {
    const r = await axios.get(url, { timeout: 15000, headers, validateStatus: () => true });
    if (r.status === 200) {
      const h = r.data;
      const dlMatches = [...h.matchAll(/href="([^"]*download[^"]*)"/gi)].map(m => m[1]);
      const sizeMatch = h.match(/(\d+(?:\.\d+)?)\s*(M|K)/);
      return { status: 200, dlLinks: dlMatches.slice(0, 3), size: sizeMatch ? sizeMatch[0] : '?' };
    }
    return { status: r.status };
  } catch (e) {
    return { error: e.message };
  }
}

async function main() {
  const urls = [
    'https://www.roms2000.com/senryaku-shougi-playstation-rom',
    'https://www.roms2000.com/poketan-playstation-rom',
    'https://www.roms2000.com/soukyuu-gurentai-oubushutsugeki-playstation-rom',
    'https://www.roms2000.com/pacapaca-passion-special-playstation-rom',
    'https://www.roms2000.com/arcade-hits-soukyuu-gurentai-playstation-rom',
    'https://www.roms2000.com/mouja-playstation-rom',
    'https://www.roms2000.com/hoissuru-playstation-rom'
  ];

  for (const url of urls) {
    const result = await checkUrl(url);
    const name = url.split('/').pop().replace('-playstation-rom', '');
    if (result.status === 200) {
      console.log(name, '-> FOUND!', 'Size:', result.size, 'DL:', result.dlLinks);
    } else {
      console.log(name, '->', result.status || result.error);
    }
  }
}
main();
