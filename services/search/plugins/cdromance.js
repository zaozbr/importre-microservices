// cdromance.org - download via ticket POST
// 1. GET pagina do jogo -> extrai span#obfuscatedId (ticket)
// 2. POST cdromance.org com cdrTicketInput={ticket}
// 3. Extrai link dl{N}.cdromance.com/download.php?file=...&id=...&key=...
const axios = require('axios');
const cheerio = require('cheerio');
const { buildSource } = require('./_base');

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.5',
};

module.exports = {
  name: 'cdromance',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 7,
  enabled: true,
  async search(serial, title) {
    if (!title) return [];
    try {
      // Busca na lista de PSX
      const q = encodeURIComponent(title.split('(')[0].trim());
      const searchUrl = `https://cdromance.org/?s=${q}`;
      const res = await axios.get(searchUrl, { headers: HEADERS, timeout: 15000 });
      const $ = cheerio.load(res.data);
      
      // Procura links para paginas de jogos
      const gameLinks = [];
      $('a[href*="psx-iso"]').each((i, el) => {
        const href = $(el).attr('href');
        if (href && href.includes('cdromance.org') && !href.includes('?s=') && !gameLinks.includes(href)) {
          gameLinks.push(href);
        }
      });
      
      if (!gameLinks.length) return [];
      
      // Acessa a primeira pagina de jogo e extrai o ticket
      const gameUrl = gameLinks[0];
      const gameRes = await axios.get(gameUrl, { headers: HEADERS, timeout: 15000 });
      const $game = cheerio.load(gameRes.data);
      
      // Extrai ticket do span#obfuscatedId
      const ticket = $game('#obfuscatedId').text().trim();
      if (!ticket) return [];
      
      // POST para obter link de download
      const postRes = await axios.post('https://cdromance.org/', 
        `cdrTicketInput=${ticket}`, 
        {
          headers: { ...HEADERS, 'Content-Type': 'application/x-www-form-urlencoded', 'Referer': gameUrl },
          timeout: 15000,
          maxRedirects: 5
        }
      );
      
      const $dl = cheerio.load(postRes.data);
      const sources = [];
      const seen = new Set();
      
      // Extrai links dl{N}.cdromance.com/download.php
      $dl('a[href*="cdromance.com/download.php"]').each((i, el) => {
        const href = $(el).attr('href');
        if (href && !seen.has(href)) {
          seen.add(href);
          sources.push(buildSource('cdromance', href, title, { 
            headers: { 'Referer': gameUrl }
          }));
        }
      });
      
      return sources.slice(0, 3);
    } catch (e) {
      return [];
    }
  }
};
