// romsfun.com - busca por titulo, download via sto.romsfast.com
// 1. GET https://romsfun.com/roms/playstation/?s={title} -> extrai links /roms/playstation/{slug}.html
// 2. GET pagina do jogo -> extrai link /download/{slug}-{id}
// 3. GET /download/{slug}-{id}/1 -> extrai URL direta em sto.romsfast.com
const axios = require('axios');
const cheerio = require('cheerio');
const { normalize, titleScore, buildSource } = require('./_base');

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.5',
};

const ROMSFUN_BASE = 'https://romsfun.com';
const ROMSFUN_PSX_SEARCH = 'https://romsfun.com/roms/playstation/?s=';

function extractGameLinks(html) {
  const $ = cheerio.load(html);
  const links = [];
  const seen = new Set();
  $('a[href*="/roms/playstation/"]').each((_, el) => {
    const href = $(el).attr('href');
    if (!href || href.includes('?s=') || href.includes('/page/') || seen.has(href)) return;
    if (href.endsWith('.html') && href.includes('romsfun.com/roms/playstation/')) {
      seen.add(href);
      links.push(href);
    }
  });
  return links;
}

async function extractDownloadPageUrl(gameUrl) {
  const res = await axios.get(gameUrl, { headers: HEADERS, timeout: 15000 });
  const $ = cheerio.load(res.data);
  // Link de download: /download/{slug}-{id}
  let dlUrl = $('a[href*="/download/"]').first().attr('href');
  if (!dlUrl) {
    const match = res.data.match(/href="(https?:\/\/romsfun\.com\/download\/[^"]+)"/);
    if (match) dlUrl = match[1];
  }
  if (!dlUrl) return null;
  if (dlUrl.startsWith('/')) dlUrl = ROMSFUN_BASE + dlUrl;
  return dlUrl;
}

async function extractDirectUrl(downloadPageUrl) {
  // Tenta mirrors 1, 2, 3
  for (let mirror = 1; mirror <= 3; mirror++) {
    try {
      const url = `${downloadPageUrl}/${mirror}`;
      const res = await axios.get(url, { headers: HEADERS, timeout: 15000, maxRedirects: 5 });
      // Procura URL direta em sto.romsfast.com ou similar
      const dlMatch = res.data.match(/href="(https?:\/\/[^"]*\.(7z|zip|rar|iso|bin|cue|img|chd)[^"]*)"/i);
      if (dlMatch) return dlMatch[1];
      // Procura qualquer link externo com extensao de ROM
      const extMatch = res.data.match(/href="(https?:\/\/(?!romsfun\.com)[^"]*\.(7z|zip|rar|iso|bin|cue|img|chd)[^"]*)"/i);
      if (extMatch) return extMatch[1];
    } catch (e) {
      // tenta proximo mirror
    }
  }
  return null;
}

module.exports = {
  name: 'romsfun',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 9,
  enabled: true,
  async search(serial, title) {
    if (!title) return [];
    try {
      const query = encodeURIComponent(title.split('(')[0].trim());
      const searchUrl = ROMSFUN_PSX_SEARCH + query;
      const searchRes = await axios.get(searchUrl, { headers: HEADERS, timeout: 15000 });
      const gameLinks = extractGameLinks(searchRes.data);
      if (!gameLinks.length) return [];

      const target = normalize(title);
      const sources = [];
      const modSources = [];
      for (const gameUrl of gameLinks.slice(0, 5)) {
        try {
          const dlPageUrl = await extractDownloadPageUrl(gameUrl);
          if (!dlPageUrl) continue;
          const directUrl = await extractDirectUrl(dlPageUrl);
          if (!directUrl) continue;
          // Extrai titulo da URL do jogo
          const gameTitle = gameUrl.split('/').pop().replace('.html', '').replace(/-/g, ' ');
          const score = titleScore(target, normalize(gameTitle));
          if (score >= 0.5) {
            const src = buildSource('romsfun', directUrl, title, { score, referer: gameUrl });
            // Prioriza ROMs originais (/PSX/) sobre mods (/Mods/)
            if (directUrl.includes('/PSX/') || directUrl.includes('/psx/')) {
              sources.push(src);
            } else {
              modSources.push(src);
            }
          }
        } catch (e) {
          // continua para proximo jogo
        }
      }
      // ROMs originais primeiro, depois mods como fallback
      return [...sources, ...modSources].slice(0, 3);
    } catch (e) {
      return [];
    }
  }
};
