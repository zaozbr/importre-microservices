// romsretro.com - link direto dl.romsretro.com/roms/{nome}[romsretro.com].zip
const axios = require('axios');
const cheerio = require('cheerio');
const { buildSource } = require('./_base');

module.exports = {
  name: 'romsretro',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 6,
  enabled: true,
  async search(serial, title) {
    if (!title) return [];
    try {
      // Busca no site por titulo
      const q = encodeURIComponent(title.split('(')[0].trim());
      const url = `https://romsretro.com/?s=${q}`;
      const res = await axios.get(url, {
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
        timeout: 12000
      });
      const $ = cheerio.load(res.data);
      const sources = [];
      const seen = new Set();
      
      // Procura links para páginas de jogos
      $('a[href*="romsretro.com/"]').each((i, el) => {
        const href = $(el).attr('href');
        if (!href || seen.has(href)) return;
        if (href.includes('/roms/psx/') || href.includes('/roms/') && !href.includes('?s=')) {
          seen.add(href);
        }
      });
      
      // Para cada página de jogo encontrada, extrai link de download
      const pageUrls = [...seen].slice(0, 3);
      for (const pageUrl of pageUrls) {
        try {
          const pageRes = await axios.get(pageUrl, {
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
            timeout: 12000
          });
          const $page = cheerio.load(pageRes.data);
          // Link direto: dl.romsretro.com/roms/{nome}[romsretro.com].zip
          $page('a[href*="dl.romsretro.com"]').each((i, el) => {
            const dlUrl = $(el).attr('href');
            if (dlUrl && /\.(zip|7z|rar|iso)$/i.test(dlUrl)) {
              sources.push(buildSource('romsretro', dlUrl, title, { 
                headers: { 'Referer': 'https://romsretro.com/' }
              }));
            }
          });
          if (sources.length > 0) return sources;
        } catch (e) {}
      }
      return sources;
    } catch (e) {
      return [];
    }
  }
};
