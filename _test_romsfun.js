const axios = require('axios');
const cheerio = require('cheerio');

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.5',
};

const ROMSFUN_PSX_SEARCH = 'https://romsfun.com/roms/playstation/?s=';

async function test() {
  const titles = ['Motocross Madness', 'Wing Commander IV', 'Disney Anastasia', 'Goldie', 'Crash Bandicoot'];
  for (const title of titles) {
    try {
      const query = encodeURIComponent(title.split('(')[0].trim());
      const searchUrl = ROMSFUN_PSX_SEARCH + query;
      console.log(`\n=== ${title} ===`);
      console.log(`URL: ${searchUrl}`);
      const res = await axios.get(searchUrl, { headers: HEADERS, timeout: 15000 });
      console.log(`Status: ${res.status} | Length: ${res.data.length}`);
      const $ = cheerio.load(res.data);
      const links = [];
      $('a[href*="/roms/playstation/"]').each((_, el) => {
        const href = $(el).attr('href');
        if (!href || href.includes('?s=') || href.includes('/page/')) return;
        if (href.endsWith('.html') && href.includes('romsfun.com/roms/playstation/')) {
          links.push(href);
        }
      });
      console.log(`Links encontrados: ${links.length}`);
      links.slice(0, 3).forEach(l => console.log(`  ${l}`));
      if (links.length === 0) {
        // Verificar se a pagina mudou
        const title2 = $('title').text();
        console.log(`Title da pagina: ${title2}`);
        // Procurar qualquer link
        const allLinks = [];
        $('a').each((_, el) => {
          const href = $(el).attr('href');
          if (href && href.includes('romsfun.com')) allLinks.push(href);
        });
        console.log(`Todos links romsfun: ${allLinks.length}`);
        allLinks.slice(0, 5).forEach(l => console.log(`  ${l}`));
      }
    } catch (e) {
      console.log(`ERRO: ${e.message}`);
    }
  }
}
test();
