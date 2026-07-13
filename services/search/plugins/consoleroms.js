const axios = require('axios');
const cheerio = require('cheerio');
const { normalize, titleScore, buildSource } = require('./_base');

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.5',
};

const CONSOLEROMS_BASE = 'https://www.consoleroms.com';

// Extrai links de jogos PSX da pagina de busca ou listagem
function extractGameLinks(html) {
  const $ = cheerio.load(html);
  const links = [];
  const seen = new Set();
  $('a[href*="/roms/psx/"]').each((_, el) => {
    const href = $(el).attr('href');
    if (!href) return;
    // So paginas de jogo (nao /page/ nem /download nem categorias)
    if (href.includes('/page/') || href.endsWith('/roms/psx') || href.endsWith('/roms/psx/')) return;
    if (href.includes('/download')) return;
    const full = href.startsWith('http') ? href : CONSOLEROMS_BASE + href;
    if (seen.has(full)) return;
    seen.add(full);
    // Tenta extrair nome do link ou do href
    let text = $(el).text().trim();
    if (!text || text === 'View' || text.length < 3) {
      // Deriva nome do slug da URL
      const slug = full.split('/').pop();
      text = slug.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }
    if (text && text.length > 2) links.push({ url: full, name: text });
  });
  return links;
}

// Resolve a pagina do jogo para extrair o link /download
async function resolveDownloadPage(gameUrl) {
  try {
    const res = await axios.get(gameUrl, { headers: HEADERS, timeout: 15000 });
    const $ = cheerio.load(res.data);
    // Link de download: /roms/psx/{slug}/download
    let dlUrl = $('a[href*="/download"]').first().attr('href');
    if (!dlUrl) {
      const match = res.data.match(/href="([^"]*\/roms\/psx\/[^"]*\/download[^"]*)"/);
      if (match) dlUrl = match[1];
    }
    if (!dlUrl) return null;
    return dlUrl.startsWith('http') ? dlUrl : CONSOLEROMS_BASE + dlUrl;
  } catch (e) {
    return null;
  }
}

// Resolve o endpoint /download para URL direta do arquivo
async function resolveDirectUrl(downloadUrl) {
  try {
    const res = await axios.get(downloadUrl, {
      headers: HEADERS,
      timeout: 15000,
      maxRedirects: 10,
    });
    const html = res.data;
    // Procura URL direta com extensao de ROM em href
    const dlMatch = html.match(/href="(https?:\/\/[^"]*\.(7z|zip|rar|iso|bin|cue|img|chd)[^"]*)"/i);
    if (dlMatch) return dlMatch[1];
    // Procura window.location.href = "..." (consoleroms usa isso para redirect)
    const jsMatch = html.match(/window\.location\.href\s*=\s*["']([^"']+)["']/);
    if (jsMatch) {
      const target = jsMatch[1];
      // Se ja aponta para arquivo com extensao de ROM, retorna direto
      if (/\.(7z|zip|rar|iso|bin|cue|img|chd)/i.test(target)) return target;
      // Caso contrario, segue o redirect
      const targetUrl = target.startsWith('http') ? target : CONSOLEROMS_BASE + target;
      return await resolveDirectUrl(targetUrl);
    }
    // Procura meta refresh redirect
    const metaMatch = html.match(/<meta[^>]+refresh[^>]+url=([^"'>]+)/i);
    if (metaMatch) {
      const target = metaMatch[1].trim();
      if (/\.(7z|zip|rar|iso|bin|cue|img|chd)/i.test(target)) return target;
      const targetUrl = target.startsWith('http') ? target : CONSOLEROMS_BASE + target;
      return await resolveDirectUrl(targetUrl);
    }
    // Procura qualquer link externo com extensao de ROM
    const extMatch = html.match(/href="(https?:\/\/(?!consoleroms\.com)[^"]*\.(7z|zip|rar|iso|bin|cue|img|chd)[^"]*)"/i);
    if (extMatch) return extMatch[1];
    return null;
  } catch (e) {
    return null;
  }
}

module.exports = {
  name: 'consoleroms',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 13,
  enabled: true,
  async search(serial, title) {
    if (!title) return [];
    try {
      // Busca por titulo no site
      const query = encodeURIComponent(title.split('(')[0].split('[')[0].trim());
      if (query.length < 3) return [];

      const searchUrl = `${CONSOLEROMS_BASE}/roms/psx?q=${query}`;
      const res = await axios.get(searchUrl, { headers: HEADERS, timeout: 15000 });
      let gameLinks = extractGameLinks(res.data);

      // Se a busca nao retornou nada, tenta listagem completa (pagina 1)
      if (!gameLinks.length) {
        const listRes = await axios.get(`${CONSOLEROMS_BASE}/roms/psx`, { headers: HEADERS, timeout: 15000 });
        gameLinks = extractGameLinks(listRes.data);
      }

      if (!gameLinks.length) return [];

      // Filtra por score de titulo
      const target = normalize(title);
      // Extrai numero de sequencia do titulo alvo (ex: "Crash Bandicoot 3" -> "3")
      const targetSeqMatch = target.match(/\b([23456789]|ii|iii|iv|v)\b/);
      const scored = gameLinks
        .map(g => {
          const gNorm = normalize(g.name);
          let score = titleScore(target, gNorm);
          // Penaliza sequencias diferentes: se alvo nao tem "2", rejeita "2"
          if (!targetSeqMatch) {
            const gSeqMatch = gNorm.match(/\b([23456789]|ii|iii|iv|v)\b/);
            if (gSeqMatch) score *= 0.5;
          }
          return { ...g, score };
        })
        .filter(g => g.score >= 0.6);
      scored.sort((a, b) => b.score - a.score);

      const sources = [];
      for (const game of scored.slice(0, 3)) {
        const dlPageUrl = await resolveDownloadPage(game.url);
        if (!dlPageUrl) continue;
        const directUrl = await resolveDirectUrl(dlPageUrl);
        if (!directUrl) continue;
        sources.push(buildSource('consoleroms', directUrl, title, { score: game.score, referer: game.url }));
      }
      return sources;
    } catch (e) {
      return [];
    }
  }
};
